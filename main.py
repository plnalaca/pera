from fastapi import FastAPI, HTTPException, Query
import mysql.connector
from mysql.connector import Error
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from stellar_sdk import Keypair
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend'in adresi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    try:
        connection = mysql.connector.connect(
            host="mysql",
            user="user",
            password="userpass",
            database="appdb"
        )
        return connection
    except Error as e:
        raise Exception(f"Veritabanı bağlantı hatası: {e}")

@app.get("/")
def read_root():
    return {"message": "Merhaba Göktuğ!"}

@app.get("/db-test")
def test_db_connection():
    try:
        connection = get_db()
        if connection.is_connected():
            db_info = connection.get_server_info()
            return {"status": "Bağlantı başarılı", "mysql_version": db_info}
    except Exception as e:
        return {"status": "Bağlantı başarısız", "error": str(e)}
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

def is_valid_wallet_code(wallet_code: str) -> bool:
    try:
        Keypair.from_public_key(wallet_code)
        return True
    except Exception:
        return False

class UserCreate(BaseModel):
    name: str
    surname: str
    public_key: str

@app.post("/create_user")
def create_user(user: UserCreate):
    try:
        user.public_key = user.public_key.strip()
        connection = get_db()
        cursor = connection.cursor(dictionary=True)

        # wallet_code zaten var mı?
        cursor.execute("SELECT * FROM users WHERE wallet_code = %s", (user.public_key,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Bu public_key zaten kayıtlı.")

        # Yeni kullanıcı ekle
        insert_query = """
            INSERT INTO users (name, surname, wallet_code)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (user.name, user.surname, user.public_key))
        connection.commit()

        insert_query = """
            INSERT INTO lessons (public_key, lesson)
            VALUES (%s, [])
        """
        cursor.execute(insert_query, (public_key))
        connection.commit()

        token = str(uuid4())

        return {
            "message": "Kullanıcı başarıyla oluşturuldu",
            "user": {
                "name": user.name,
                "surname": user.surname,
                "token": token,
                "public_key": user.public_key
            }
        }
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

@app.get("/check_user")
def check_user(public_key: str = Query(..., description="Kullanıcının cüzdan kodu")):
    try:
        public_key = public_key.strip()
        if is_valid_wallet_code(public_key) == False:
            return {
                "name": None,
                "surname": None,
                "token": None,
                "status": "Geçersiz Cüzdan Kodu"
            }
        connection = get_db()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT name, surname FROM users WHERE wallet_code = %s", (public_key,))
        user = cursor.fetchone()

        if user:
            token = str(uuid4())
            return {
                "name": user["name"],
                "surname": user["surname"],
                "token": token,
                "status": "başarılı"
            }
        else:
            return {
                "name": None,
                "surname": None,
                "token": None,
                "status": "başarısız"
            }

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

@app.get("/getCompletedLessons")
def get_completed_lessons(public_key: str = Query(..., description="Kullanıcının cüzdan adresi")):
    try:
        public_key = public_key.strip()

        connection = get_db()
        cursor = connection.cursor(dictionary=True)

        # Kullanıcıyı kontrol et
        cursor.execute("SELECT * FROM users WHERE wallet_code = %s", (public_key,))
        user = cursor.fetchone()

        if not user:
            return {
                "status": "kullanıcı bulunamadı",
                "public_key": public_key,
                "lessons": []
            }

        # Kullanıcının tamamladığı dersleri çek
        cursor.execute("SELECT id, creation_time, lesson FROM lessons WHERE public_key = %s", (public_key,))
        lessons = cursor.fetchall()

        return {
            "status": "başarılı",
            "public_key": public_key,
            "lesson_count": len(lessons),
            "lessons": lessons
        }

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()
