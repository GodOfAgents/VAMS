"""Kernel-enforced snapshot compatibility, including Python 3.12 symbol absence."""
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("sealing_runner", Path(__file__).with_name("f05_2a_tx_sim_runner_r3.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class SealingCompatibilityTests(unittest.TestCase):
    def test_kernel_rejects_write_grow_shrink_and_additional_seal(self):
        fd = r._sealed_snapshot("sealing-test", b"immutable")
        try:
            self.assertEqual(os.pread(fd, 9, 0), b"immutable")
            self.assertTrue(r._snapshot_still_bound(fd, b"immutable", hashlib.sha256(b"immutable").hexdigest()))
            with mock.patch.object(r.fcntl, "fcntl", return_value=0):
                self.assertFalse(r._snapshot_still_bound(fd, b"immutable", hashlib.sha256(b"immutable").hexdigest()))
            for operation in (lambda: os.pwrite(fd, b"X", 0),
                              lambda: os.ftruncate(fd, 10),
                              lambda: os.ftruncate(fd, 8),
                              lambda: r.fcntl.fcntl(fd, 1033, 16)):
                with self.subTest(operation=operation):
                    with self.assertRaises(OSError) as caught:
                        operation()
                    self.assertEqual(caught.exception.errno, errno.EPERM)
            self.assertEqual(r.fcntl.fcntl(fd, 1034) & 15, 15)
        finally:
            os.close(fd)

    def test_missing_python_symbols_still_produce_kernel_enforced_snapshot(self):
        names = ("F_ADD_SEALS", "F_GET_SEALS", "F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL")
        saved = {name: getattr(r.fcntl, name) for name in names if hasattr(r.fcntl, name)}
        try:
            for name in saved:
                delattr(r.fcntl, name)
            self.test_kernel_rejects_write_grow_shrink_and_additional_seal()
        finally:
            for name, value in saved.items():
                setattr(r.fcntl, name, value)

    def test_missing_kernel_seals_fail_closed_and_close_descriptor(self):
        fds = []
        original = os.memfd_create
        def record(*args):
            fd = original(*args)
            fds.append(fd)
            return fd
        with mock.patch.object(r.os, "memfd_create", side_effect=record), mock.patch.object(r.fcntl, "fcntl", return_value=0):
            with self.assertRaises(r.SnapshotError) as caught:
                r._sealed_snapshot("sealing-missing", b"immutable")
        self.assertEqual(caught.exception.code, "snapshot_seal_failed")
        self.assertEqual(len(fds), 1)
        with self.assertRaises(OSError):
            os.fstat(fds[0])

    def test_linux_constants_are_not_applied_to_other_platforms(self):
        with mock.patch.object(r.sys, "platform", "other"), mock.patch.object(r.os, "memfd_create") as create:
            with self.assertRaises(r.SnapshotError):
                r._sealed_snapshot("wrong-platform", b"immutable")
        create.assert_not_called()

if __name__ == "__main__":
    unittest.main()
