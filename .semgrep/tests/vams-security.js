// ruleid: vams-default-credential-js
const fallbackPassword = "vams2026";
// ok: vams-default-credential-js
if (input === "vams2026") { throw new Error("default password refused"); }
const child_process = require("child_process");
// ruleid: vams-node-child-process-shell
child_process.exec("ls " + fallbackPassword);
