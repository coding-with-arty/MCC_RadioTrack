"""
RadioTrack - Radio Inventory Management System
--------------------------------------
db_manager.py file for Streamlit UI
--------------------------------------
Author: Arthur Belanger (github.com/coding-with-arty)
Copyright (c) 2025 Arthur Belanger
All rights reserved.
"""

import sqlite3
import logging
import pandas as pd
from pathlib import Path
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Class to manage database connections and operations"""

    @staticmethod
    def get_connection():
        """Get a connection to the SQLite database with security enabled"""
        try:
            db_path = Path(__file__).parent / "inventory.db"
            conn = sqlite3.connect(str(db_path))

            # Enable security features
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            # Balance between performance and safety
            conn.execute("PRAGMA synchronous = NORMAL")
            # Increase cache size for better performance
            conn.execute("PRAGMA cache_size = 10000")
            # Use memory for temporary storage
            conn.execute("PRAGMA temp_store = MEMORY")

            # Set row factory for better data access
            conn.row_factory = sqlite3.Row

            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None

    @staticmethod
    def execute_query(query, params=(), fetch=False, commit=True):
        """Execute a SQL query with proper error handling"""
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            if not conn:
                return None if fetch else False

            cursor = conn.cursor()
            cursor.execute(query, params)

            if fetch:
                result = cursor.fetchall()
                if commit:
                    conn.commit()
                return result
            else:
                if commit:
                    conn.commit()
                return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn and commit:
                try:
                    conn.rollback()
                except:
                    pass
            return None if fetch else False

        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    @staticmethod
    def execute_df_query(query, params=()):
        """Execute a query and return results as a pandas DataFrame"""
        try:
            conn = DatabaseManager.get_connection()
            if not conn:
                return pd.DataFrame()

            df = pd.read_sql_query(query, conn, params=params)
            return df

        except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
            logger.error(f"Database error in execute_df_query: {e}")
            return pd.DataFrame()

        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass


# Database utilities consolidated from db_utils.py

class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass


@contextmanager
def db_transaction(connection):
    """Context manager for database transactions with error handling"""
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Database transaction failed: {str(e)}")
        raise DatabaseError(f"Database operation failed: {str(e)}")
    finally:
        cursor.close()


def with_connection(func):
    """Decorator to provide a database connection to a function"""
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            return func(conn, *args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"Database connection error in {
                         func.__name__}: {str(e)}")
            raise DatabaseError(f"Database connection error: {str(e)}")
        finally:
            if conn:
                conn.close()
    return wrapper


def with_retries(func):
    """Decorator to retry database operations"""
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(3):  # MAX_RETRIES = 3
            try:
                return func(*args, **kwargs)
            except (sqlite3.Error, DatabaseError) as e:
                last_error = e
                if attempt < 2:  # MAX_RETRIES - 1
                    logger.warning(
                        f"Retrying database operation ({attempt+1}/3): {str(e)}")
                else:
                    logger.error(
                        f"Database operation failed after 3 attempts: {str(e)}")
        raise DatabaseError(
            f"Database operation failed after 3 attempts: {str(last_error)}")
    return wrapper


@with_retries
@with_connection
def safe_execute(conn, query, params=None, fetch=False, fetch_one=False):
    """
    Execute a SQL query safely with error handling and retries

    Args:
        conn: Database connection
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch: Whether to fetch results
        fetch_one: Whether to fetch a single row

    Returns:
        Query results if fetch is True, otherwise None
    """
    with db_transaction(conn) as cursor:
        cursor.execute(query, params or ())

        if fetch_one:
            return cursor.fetchone()
        elif fetch:
            return cursor.fetchall()
        return None


@with_retries
@with_connection
def safe_executemany(conn, query, params_list):
    """
    Execute a SQL query with multiple parameter sets

    Args:
        conn: Database connection
        query: SQL query string
        params_list: List of parameter tuples or dicts

    Returns:
        None
    """
    with db_transaction(conn) as cursor:
        cursor.executemany(query, params_list)
    return None


@with_retries
@with_connection
def safe_execute_script(conn, script):
    """
    Execute a SQL script

    Args:
        conn: Database connection
        script: SQL script string

    Returns:
        None
    """
    with db_transaction(conn) as cursor:
        cursor.executescript(script)
    return None


def check_db_health():
    """
    Check the health of the database

    Returns:
        dict: Database health information
    """
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()

        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]

        # Check foreign key constraints
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()

        # Get database size
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        size_bytes = page_count * page_size

        # Get table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        table_info = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            table_info[table] = {"row_count": row_count}

        conn.close()

        return {
            "status": (
                "healthy" if integrity == "ok" and not fk_violations else "issues"
            ),
            "integrity": integrity,
            "foreign_key_violations": len(fk_violations),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "tables": tables,
            "table_info": table_info,
        }

    except Exception as e:
        logger.error(f"Failed to check database health: {str(e)}")
        return {"status": "error", "error": str(e)}


def initialize_db():
    """Initialize the SQLite database with required tables"""
    from auth import hash_password
    from config import DEFAULT_ADMIN

    conn = DatabaseManager.get_connection()
    if not conn:
        return

    try:
        c = conn.cursor()

        # Create items table
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            condition TEXT DEFAULT 'Good',
            notes TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Create locations table
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Create employees table with password change requirement
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            position TEXT,
            email TEXT,
            phone TEXT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            user_role TEXT DEFAULT 'employee',
            is_active BOOLEAN DEFAULT 1,
            password_change_required BOOLEAN DEFAULT 0,
            password_expiry_date DATE,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Create posts table
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_username) REFERENCES employees (username)
        )
        """
        )

        # Create login attempts table for rate limiting
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            lockout_until DATETIME,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username)
        )
        """
        )

        # Add security columns to employees table if they don't exist
        try:
            c.execute("SELECT last_password_change FROM employees LIMIT 1")
        except sqlite3.OperationalError:
            c.execute(
                "ALTER TABLE employees ADD COLUMN last_password_change DATETIME")
            c.execute(
                "ALTER TABLE employees ADD COLUMN is_approved BOOLEAN DEFAULT 1")
            logger.info("Added security columns to employees table")

        # Create default admin user if it doesn't exist
        c.execute(
            "SELECT username FROM employees WHERE username = ?",
            (DEFAULT_ADMIN["username"],),
        )
        if not c.fetchone():
            hashed_password = hash_password(DEFAULT_ADMIN["password"])
            c.execute(
                """
            INSERT INTO employees (
                first_name, last_name, position, username,
                password, user_role, password_change_required
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "Admin",
                    "User",
                    "Corrections Radio Supervisor",
                    DEFAULT_ADMIN["username"],
                    hashed_password,
                    "corrections_supervisor",
                    1,
                ),
            )

        # Add default locations if they don't exist
        default_locations = [
            ("Control Center", "Main communications control center"),
            ("Communications Room", "Radio equipment and operations room"),
            ("Tower 1", "Primary radio tower location"),
            ("Tower 2", "Secondary radio tower location"),
            ("Tower 3", "Tertiary radio tower location"),
            ("Tower 4", "Emergency backup radio tower"),
            ("Main Gate", "Main entrance security checkpoint"),
            ("North Gate", "North perimeter security checkpoint"),
            ("South Gate", "South perimeter security checkpoint"),
            ("East Gate", "East perimeter security checkpoint"),
            ("West Gate", "West perimeter security checkpoint"),
            ("Perimeter Patrol", "Mobile patrol vehicle locations"),
            ("Transport Vehicles", "Transportation and escort vehicles"),
            ("Administrative Office", "Administrative offices and records"),
            ("Maintenance Shop", "Radio repair and maintenance workshop"),
            ("Storage Warehouse", "Equipment storage and inventory warehouse"),
        ]

        for location, description in default_locations:
            c.execute("SELECT name FROM locations WHERE name = ?", (location,))
            if not c.fetchone():
                c.execute(
                    """
                INSERT INTO locations (name, description)
                VALUES (?, ?)
                """,
                    (location, description),
                )

        # Add test items if none exist
        c.execute("SELECT COUNT(*) FROM items")
        if c.fetchone()[0] == 0:
            create_sample_items(c)

        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()


def create_sample_items(cursor):
    """Create sample inventory items for testing"""
    # Sample radio equipment items grouped by category
    test_items = [
        # Portable Radios
        (
            "Portable Radios",
            "Motorola XTS 5000 Portable Radio",
            "Control Center",
            "Excellent",
            "VHF 136-174 MHz, 128 channels",
        ),
        (
            "Portable Radios",
            "Kenwood TK-3402U16P ProTalk Portable",
            "Communications Room",
            "Good",
            "UHF 400-470 MHz, 16 channels",
        ),
        (
            "Portable Radios",
            "Icom IC-F4029SDR Portable Radio",
            "North Gate",
            "Fair",
            "VHF 136-174 MHz, 128 channels",
        ),

        # Mobile Radios
        (
            "Mobile Radios",
            "Motorola CDM1550 LS+ Mobile Radio",
            "Transport Vehicles",
            "Good",
            "VHF 136-174 MHz, 160 channels",
        ),
        (
            "Mobile Radios",
            "Kenwood TM-281A Mobile Radio",
            "Perimeter Patrol",
            "Excellent",
            "VHF 136-174 MHz, 200 channels",
        ),

        # Base Station Radios
        (
            "Base Station Radios",
            "Motorola GR1225 Base Station",
            "Communications Room",
            "Good",
            "VHF 136-174 MHz, 8 channels",
        ),
        (
            "Base Station Radios",
            "Kenwood TKR-850 Base Station",
            "Tower 1",
            "Excellent",
            "UHF 400-470 MHz, 32 channels",
        ),

        # Antennas
        (
            "Antennas",
            "Larsen NMO150B VHF Antenna",
            "Tower 2",
            "Good",
            "150-174 MHz, Unity gain",
        ),
        (
            "Antennas",
            "Comet GP-9M UHF Antenna",
            "Tower 3",
            "Excellent",
            "430-440 MHz, 8.5 dBi gain",
        ),
        (
            "Antennas",
            "Diamond NR770HB Dual Band Antenna",
            "Communications Room",
            "Fair",
            "144/440 MHz, 3.0/5.5 dBi gain",
        ),

        # Batteries & Chargers
        (
            "Batteries & Chargers",
            "Motorola PMNN4407AR Battery Pack",
            "Storage Warehouse",
            "Excellent",
            "7.4V 2200mAh Li-Ion",
        ),
        (
            "Batteries & Chargers",
            "Kenwood KSC-35S Rapid Charger",
            "Control Center",
            "Good",
            "For TK series portables",
        ),
        (
            "Batteries & Chargers",
            "Icom BP-280 Battery Pack",
            "Maintenance Shop",
            "Fair",
            "7.2V 1650mAh Ni-MH",
        ),

        # Microphones
        (
            "Microphones",
            "Motorola HMN1080B Speaker Microphone",
            "Control Center",
            "Good",
            "IP57 rated, noise canceling",
        ),
        (
            "Microphones",
            "Kenwood KMC-45 Speaker Microphone",
            "Communications Room",
            "Excellent",
            "Heavy duty, IP55 rated",
        ),

        # Cables & Accessories
        (
            "Cables & Accessories",
            "RG-213 Coaxial Cable 50ft",
            "Storage Warehouse",
            "Good",
            "Low loss, PL-259 connectors",
        ),
        (
            "Cables & Accessories",
            "Antenna Mount NMO Type",
            "Maintenance Shop",
            "Excellent",
            "Stainless steel, weather resistant",
        ),

        # Test Equipment
        (
            "Test Equipment",
            "Motorola R2670B Service Monitor",
            "Maintenance Shop",
            "Fair",
            "30-1000 MHz, spectrum analyzer",
        ),
        (
            "Test Equipment",
            "Bird 43 Wattmeter",
            "Communications Room",
            "Good",
            "RF power measurement 0.45-2700 MHz",
        ),

        # Programming Equipment
        (
            "Programming Equipment",
            "Motorola RIB Programming Box",
            "Maintenance Shop",
            "Excellent",
            "Radio Interface Box with cables",
        ),
        (
            "Programming Equipment",
            "Kenwood KPG-111D Programming Software",
            "Administrative Office",
            "Good",
            "Version 3.0 with USB interface",
        ),
    ]

    cursor.executemany(
        """
        INSERT INTO items (category, name, location, condition, notes)
        VALUES (?, ?, ?, ?, ?)
    """,
        test_items,
    )


def update_database_schema():
    """Update the database schema with new tables and columns"""
    from config import CATEGORIES, LOCATIONS

    logger.debug(f"Starting schema update with categories: {CATEGORIES}")
    logger.debug(f"Starting schema update with locations: {LOCATIONS}")

    conn = DatabaseManager.get_connection()
    if not conn:
        logger.error("Failed to get database connection for schema update")
        return False

    try:
        db_path = Path(__file__).parent / "inventory.db"
        logger.debug(f"Database path: {db_path}")
        logger.debug(f"Database exists: {db_path.exists()}")
        logger.debug(f"Database writable: {os.access(db_path, os.W_OK)}")

        c = conn.cursor()

        # Check if the is_approved column exists in employees table
        try:
            c.execute("SELECT is_approved FROM employees LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            logger.info("Adding is_approved column to employees table")
            c.execute(
                """
            ALTER TABLE employees ADD COLUMN is_approved BOOLEAN DEFAULT 0
            """
            )

            # Set existing users as approved
            c.execute(
                """
            UPDATE employees SET is_approved = 1
            """
            )

        # Update categories in the database
        try:
            # First check if categories table exists
            c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
            )
            if not c.fetchone():
                # Create categories table if it doesn't exist
                logger.info("Creating categories table")
                c.execute(
                    """
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
                )

            # Add radio-specific categories
            for category in CATEGORIES:
                try:
                    c.execute(
                        "INSERT INTO categories (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                        (category,),
                    )
                except sqlite3.Error as e:
                    # Handle SQLite versions that don't support ON CONFLICT DO NOTHING
                    try:
                        c.execute(
                            "INSERT INTO categories (name) VALUES (?)", (category,)
                        )
                    except sqlite3.IntegrityError:
                        # Category already exists
                        pass
        except sqlite3.Error as e:
            logger.error(f"Error updating categories: {e}")

        # Update locations in the database
        try:
            # First check if locations table exists
            c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
            )
            if c.fetchone():
                # Add corrections-specific locations
                for location in LOCATIONS:
                    try:
                        c.execute(
                            "INSERT INTO locations (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                            (location,),
                        )
                    except sqlite3.Error as e:
                        # Handle SQLite versions that don't support ON CONFLICT DO NOTHING
                        try:
                            c.execute(
                                "INSERT INTO locations (name) VALUES (?)", (location,)
                            )
                        except sqlite3.IntegrityError:
                            # Location already exists
                            pass
        except sqlite3.Error as e:
            logger.error(f"Error updating locations: {e}")

        conn.commit()
        logger.info("Database schema updated successfully")
    except sqlite3.Error as e:
        logger.error(f"Database schema update error: {e}")
        conn.rollback()
    finally:
        conn.close()
