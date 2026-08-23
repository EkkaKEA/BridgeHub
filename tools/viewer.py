# viewer.py
import streamlit as st
import duckdb
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bridgehub.duckdb")

db_file = st.text_input("Путь к БД", DB_PATH)

if not os.path.exists(db_file):
    st.error(f"Файл не найден: {db_file}")
    st.stop()

con = duckdb.connect(db_file, read_only=True)
tables = con.execute("SHOW TABLES").fetchdf()["name"].tolist()

if not tables:
    st.warning("В базе данных нет таблиц")
    st.stop()

table = st.selectbox("Таблица", tables)
st.dataframe(con.execute(f'SELECT * FROM "{table}"').fetchdf())
con.close()
