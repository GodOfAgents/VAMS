"""
VAMS Neuron Local Storage
=========================
SQLite-based local storage for heartbeats and metrics.
Heartbeats are stored locally and synced to gateway when available.
"""

import sqlite3
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from config import DATABASE_PATH


class NeuronStorage:
    """Local SQLite storage for neuron data."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Heartbeats table - stores telemetry when gateway is offline
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    node_id TEXT NOT NULL,
                    block_height INTEGER NOT NULL,
                    network TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    synced_at REAL
                )
            ''')
            
            # Metrics table - tracks node statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL
                )
            ''')
            
            # Node info table - stores node identity info
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS node_info (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            
            conn.commit()
    
    def store_heartbeat(
        self,
        node_id: str,
        block_height: int,
        network: str,
        payload: str,
        signature: str
    ) -> int:
        """Store a heartbeat locally."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO heartbeats 
                (timestamp, node_id, block_height, network, payload, signature)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (time.time(), node_id, block_height, network, payload, signature))
            conn.commit()
            return cursor.lastrowid
    
    def get_unsynced_heartbeats(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get heartbeats that haven't been synced to the gateway."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, node_id, block_height, network, payload, signature
                FROM heartbeats
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_synced(self, heartbeat_ids: List[int]):
        """Mark heartbeats as synced to gateway."""
        if not heartbeat_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(heartbeat_ids))
            cursor.execute(f'''
                UPDATE heartbeats 
                SET synced = 1, synced_at = ?
                WHERE id IN ({placeholders})
            ''', [time.time()] + heartbeat_ids)
            conn.commit()
    
    def record_metric(self, name: str, value: float):
        """Record a metric value."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO metrics (timestamp, metric_name, metric_value)
                VALUES (?, ?, ?)
            ''', (time.time(), name, value))
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total heartbeats
            cursor.execute('SELECT COUNT(*) FROM heartbeats')
            total_heartbeats = cursor.fetchone()[0]
            
            # Synced vs unsynced
            cursor.execute('SELECT COUNT(*) FROM heartbeats WHERE synced = 1')
            synced_heartbeats = cursor.fetchone()[0]
            
            # Latest block seen
            cursor.execute('SELECT MAX(block_height) FROM heartbeats')
            latest_block = cursor.fetchone()[0] or 0
            
            # First heartbeat time (for uptime calculation)
            cursor.execute('SELECT MIN(timestamp) FROM heartbeats')
            first_heartbeat = cursor.fetchone()[0]
            
            uptime_seconds = 0
            if first_heartbeat:
                uptime_seconds = time.time() - first_heartbeat
            
            return {
                'total_heartbeats': total_heartbeats,
                'synced_heartbeats': synced_heartbeats,
                'pending_sync': total_heartbeats - synced_heartbeats,
                'latest_block': latest_block,
                'uptime_seconds': uptime_seconds,
                'uptime_human': self._format_uptime(uptime_seconds)
            }
    
    def set_node_info(self, key: str, value: str):
        """Store node info (key-value)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO node_info (key, value)
                VALUES (?, ?)
            ''', (key, value))
            conn.commit()
    
    def get_node_info(self, key: str) -> Optional[str]:
        """Retrieve node info by key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM node_info WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format seconds into human-readable uptime."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}d {hours}h"


# Convenience function
def get_storage() -> NeuronStorage:
    """Get a storage instance."""
    return NeuronStorage()
