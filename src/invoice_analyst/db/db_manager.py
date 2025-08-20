import sqlite3


class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @property
    def conn(self):
        """Return a new sqlite3 connection (for use with pandas)."""
        return sqlite3.connect(self.db_path)

    def execute_query(
        self,
        query: str,
        params: tuple = (),
        fetch: str = None,
        return_lastrowid: bool = False,
    ):
        """Generic executor with error handling."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch == "one":
                    return cursor.fetchone()
                elif fetch == "all":
                    return cursor.fetchall()

                conn.commit()

                if return_lastrowid:
                    return cursor.lastrowid

        except sqlite3.IntegrityError as e:
            print(f"❌ Integrity error: {e}")  # duplicate, foreign key, etc.
            return None
        except sqlite3.OperationalError as e:
            print(f"⚠️ Operational error: {e}")  # bad SQL, table missing, etc.
            return None
        except Exception as e:
            print(f"🔥 Unexpected error: {e}")
            return None

    # --- CRUD ---
    def add_row(self, table: str, columns: list[str], values: list):
        cols = ", ".join(columns)
        placeholders = ", ".join("?" for _ in values)
        query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        return self.execute_query(query, tuple(values), return_lastrowid=True)

    def update_row(self, table: str, row_id: int, updates: dict):
        set_clause = ", ".join(f"{col}=?" for col in updates.keys())
        query = f"UPDATE {table} SET {set_clause} WHERE id=?"
        params = tuple(updates.values()) + (row_id,)
        return self.execute_query(query, params)

    def delete_row(self, table: str, row_id: int):
        query = f"DELETE FROM {table} WHERE id=?"
        return self.execute_query(query, (row_id,))

    def delete_rows(self, table: str, where: str = None, params: tuple = ()):
        query = f"DELETE FROM {table}"
        if where:
            query += f" WHERE {where}"
        return self.execute_query(query, params)

    def get_row(self, table: str, row_id: int):
        query = f"SELECT * FROM {table} WHERE id=?"
        return self.execute_query(query, (row_id,), fetch="one")

    def get_rows(self, table: str, where: str = None, params: tuple = ()):
        query = f"SELECT * FROM {table}"
        if where:
            query += f" WHERE {where}"
        return self.execute_query(query, params, fetch="all")

    def get_or_create_row(
        self, table: str, unique_fields: dict, extra_fields: dict = None
    ):
        """
        Try to get a row based on unique_fields.
        If not found, insert a new one with unique_fields + extra_fields.
        Returns the row id.
        """
        where_clause = " AND ".join(f"{col}=?" for col in unique_fields.keys())
        select_query = f"SELECT id FROM {table} WHERE {where_clause}"
        row = self.execute_query(
            select_query, tuple(unique_fields.values()), fetch="one"
        )

        if row:  # found existing
            return row[0]

        # not found → insert new
        insert_data = {**unique_fields, **(extra_fields or {})}
        return self.add_row(table, list(insert_data.keys()), list(insert_data.values()))

    def get_column_names(self, table: str):
        """Get column names for a given table."""
        query = f"PRAGMA table_info({table})"
        rows = self.execute_query(query, fetch="all")
        return [row[1] for row in rows] if rows else []
