"""Database initialization and connection management.

This module provides database connection management, schema initialization,
and sample data loading for the library management system.
"""
import csv
import os
import sqlite3
from typing import Optional

from flask import g

from config.config import Config


def get_db() -> sqlite3.Connection:
    """Get database connection from Flask application context.

    Returns:
        SQLite database connection with Row factory enabled.
    """
    if 'db' not in g:
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        g.db = sqlite3.connect(
            Config.DATABASE_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database with schema"""
    db = get_db()
    
    # Create users table
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            birthday TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            member_since TEXT NOT NULL,
            is_locked INTEGER DEFAULT 0,
            fines REAL DEFAULT 0.0,
            violations INTEGER DEFAULT 0,
            favorites TEXT DEFAULT '[]'
        )
    ''')
    
    # Create books table
    db.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            publisher TEXT NOT NULL,
            year INTEGER NOT NULL,
            language TEXT NOT NULL,
            isbn TEXT NOT NULL,
            description TEXT,
            cover_url TEXT,
            total_copies INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 1,
            shelf_location TEXT,
            rating REAL DEFAULT 0.0,
            borrow_count INTEGER DEFAULT 0
        )
    ''')
    
    # Create borrows table - FIXED: Added missing columns
    db.execute('''
        CREATE TABLE IF NOT EXISTS borrows (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            borrow_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT NOT NULL DEFAULT 'waiting',
            renewed_count INTEGER DEFAULT 0,
            pending_until TEXT,
            condition TEXT,
            damage_fee REAL DEFAULT 0.0,
            late_fee REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    ''')
    
    # Create reviews table
    db.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    ''')
    
    # Create reservations table - FIXED: ADDED NEW TABLE
    db.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            reservation_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            notified_date TEXT,
            hold_until TEXT,
            queue_position INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    ''')
    
    # Create violations_history table - FIXED: ADDED NEW TABLE
    db.execute('''
        CREATE TABLE IF NOT EXISTS violations_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            borrow_id TEXT,
            violation_type TEXT NOT NULL,
            description TEXT,
            fine_amount REAL NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            violation_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (borrow_id) REFERENCES borrows (id)
        )
    ''')
    
    # Create notifications table
    db.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            date TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create chat_messages table
    db.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    
    # Create system_config table
    db.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY,
            config_data TEXT NOT NULL
        )
    ''')
    
    # Create system_logs table
    db.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            log_type TEXT DEFAULT 'info',
            user_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    db.commit()
    
    # Insert mock data
    insert_mock_data(db)


def insert_mock_data(db):
    """Insert mock data for testing"""
    import json
    from datetime import datetime
    import uuid
    from werkzeug.security import generate_password_hash
    
    # Check if data already exists
    cursor = db.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] > 0:
        return  # Data already exists
    
    # Insert demo users
    users = [
        {
            'id': str(uuid.uuid4()),
            'email': 'user@library.com',
            'password': generate_password_hash('user123'),
            'name': 'John Doe',
            'phone': '0123456789',
            'birthday': '1990-01-15',
            'role': 'user',
            'member_since': '2024-01-01',
            'is_locked': 0,
            'fines': 0.0,
            'violations': 0,
            'favorites': '[]'
        },
        {
            'id': str(uuid.uuid4()),
            'email': 'staff@library.com',
            'password': generate_password_hash('staff123'),
            'name': 'Jane Smith',
            'phone': '0987654321',
            'birthday': '1985-05-20',
            'role': 'staff',
            'member_since': '2023-01-01',
            'is_locked': 0,
            'fines': 0.0,
            'violations': 0,
            'favorites': '[]'
        },
        {
            'id': str(uuid.uuid4()),
            'email': 'admin@library.com',
            'password': generate_password_hash('admin123'),
            'name': 'Admin User',
            'phone': '0111222333',
            'birthday': '1980-03-10',
            'role': 'admin',
            'member_since': '2022-01-01',
            'is_locked': 0,
            'fines': 0.0,
            'violations': 0,
            'favorites': '[]'
        }
    ]
    
    for user in users:
        db.execute('''
            INSERT INTO users (id, email, password, name, phone, birthday, role, 
                             member_since, is_locked, fines, violations, favorites)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user['id'], user['email'], user['password'], user['name'], 
              user['phone'], user['birthday'], user['role'], user['member_since'],
              user['is_locked'], user['fines'], user['violations'], user['favorites']))
    
    # Load books from CSV file
    books = []
    csv_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'books_clean_top100_1.csv')
    
    try:
        with open(csv_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
            csv_reader = csv.DictReader(f)
            for i, row in enumerate(csv_reader):
                if i >= 100:  # Limit to 100 books
                    break
                
                # Skip rows with empty title
                if not row.get('title') or not row['title'].strip():
                    continue
                    
                # Extract year from publisher or set default
                year = 2020
                isbn = row.get('isbn', '').strip()
                if isbn and len(isbn) >= 4:
                    try:
                        # Try to extract year from ISBN or set based on index
                        year = 2024 - (i % 50)  # Vary years from 1974-2024
                    except:
                        year = 2020
                
                # Generate shelf location
                shelf_location = f"{chr(65 + (i % 26))}-{(i // 26) + 1:02d}-{(i % 10) + 1}"
                
                books.append({
                    'id': str(uuid.uuid4()),
                    'title': row.get('title', 'Unknown').strip()[:200],
                    'author': row.get('authors', 'Unknown').strip()[:100],
                    'category': row.get('Genre', 'General').strip()[:50],
                    'publisher': row.get('publisher', 'Unknown').strip()[:100],
                    'year': year,
                    'language': 'English',
                    'isbn': isbn[:50] if isbn else f'ISBN-{i:05d}',
                    'description': f"A {row.get('Genre', 'book').lower()} by {row.get('authors', 'Unknown')}. Published by {row.get('publisher', 'Unknown')}.",
                    'cover_url': row.get('cover_url', 'https://via.placeholder.com/400x600?text=No+Cover').strip(),
                    'total_copies': 3 + (i % 5),  # 3-7 copies
                    'available_copies': 2 + (i % 4),  # 2-5 available
                    'shelf_location': shelf_location,
                    'rating': round(3.5 + (i % 15) / 10, 1),  # Rating 3.5-5.0
                    'borrow_count': (i * 7) % 500  # Varied borrow count
                })
    except FileNotFoundError:
        print(f"Warning: CSV file not found at {csv_file}. Using fallback books.")
        # Fallback to a few demo books if CSV not found
        books = [
            {
                'id': str(uuid.uuid4()),
                'title': 'The Great Gatsby',
                'author': 'F. Scott Fitzgerald',
                'category': 'Classic Literature',
                'publisher': 'Scribner',
                'year': 1925,
                'language': 'English',
                'isbn': '978-0-7432-7356-5',
                'description': 'A masterpiece of American literature set in the Jazz Age.',
                'cover_url': 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=400&h=600&fit=crop',
                'total_copies': 5,
                'available_copies': 2,
                'shelf_location': 'A-12-3',
                'rating': 4.5,
                'borrow_count': 342
            },
            {
                'id': str(uuid.uuid4()),
                'title': '1984',
                'author': 'George Orwell',
                'category': 'Science Fiction',
                'publisher': 'Secker & Warburg',
                'year': 1949,
                'language': 'English',
                'isbn': '978-0-452-28423-4',
                'description': 'A dystopian social science fiction novel.',
                'cover_url': 'https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=400&h=600&fit=crop',
                'total_copies': 6,
                'available_copies': 4,
                'shelf_location': 'B-05-2',
                'rating': 4.7,
                'borrow_count': 412
            }
        ]
    
    for book in books:
        db.execute('''
            INSERT INTO books (id, title, author, category, publisher, year, language,
                             isbn, description, cover_url, total_copies, available_copies,
                             shelf_location, rating, borrow_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (book['id'], book['title'], book['author'], book['category'], 
              book['publisher'], book['year'], book['language'], book['isbn'],
              book['description'], book['cover_url'], book['total_copies'],
              book['available_copies'], book['shelf_location'], book['rating'],
              book['borrow_count']))
    
    db.commit()