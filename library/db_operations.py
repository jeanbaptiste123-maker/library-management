# library/db_operations.py
from .db_config import Database
from datetime import datetime, timedelta, date
import random
import string

# ==================== HELPER FUNCTIONS ====================
def dictfetchall(cursor):
    """Return all rows from cursor as a dictionary"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dictfetchone(cursor):
    """Return one row from cursor as a dictionary"""
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

class LibraryDB:
    
    # ==================== AUTHENTICATION ====================
    @staticmethod
    def authenticate_user(username, password):
        """Login authentication"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, full_name, email, role, is_active 
                FROM users 
                WHERE username = %s AND password = %s AND is_active = 1
            """, (username, password))
            user = dictfetchone(cursor)
            
            if user:
                cursor.fetchall()
                cursor.execute(
                    "UPDATE users SET last_login = NOW() WHERE id = %s",
                    (user['id'],)
                )
                conn.commit()
            return user
    
    @staticmethod
    def register_student(username, password, email, full_name, phone, student_id, department, semester):
        """Register new student"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Check if username exists
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    return False, "Username already exists"
                cursor.fetchall()
                
                # Check if email exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    return False, "Email already exists"
                cursor.fetchall()
                
                # Check if student_id exists
                cursor.execute("SELECT id FROM students WHERE student_id = %s", (student_id,))
                if cursor.fetchone():
                    return False, "Student ID already exists"
                cursor.fetchall()
                
                # Insert user
                cursor.execute("""
                    INSERT INTO users (username, password, email, full_name, phone, role)
                    VALUES (%s, %s, %s, %s, %s, 'student')
                """, (username, password, email, full_name, phone))
                user_id = cursor.lastrowid
                
                # Insert student details
                cursor.execute("""
                    INSERT INTO students (user_id, student_id, department, semester, year_of_study, max_books_limit, current_books_borrowed, total_books_borrowed)
                    VALUES (%s, %s, %s, %s, %s, 5, 0, 0)
                """, (user_id, student_id, department, semester, 1))
                
                conn.commit()
                return True, "Registration successful"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    @staticmethod
    def add_librarian(username, password, email, full_name, phone):
        """Add new librarian (admin only)"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    return False, "Username already exists"
                cursor.fetchall()
                
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    return False, "Email already exists"
                cursor.fetchall()
                
                cursor.execute("""
                    INSERT INTO users (username, password, email, full_name, phone, role, is_active)
                    VALUES (%s, %s, %s, %s, %s, 'librarian', TRUE)
                """, (username, password, email, full_name, phone))
                conn.commit()
                return True, "Librarian added successfully"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    # ==================== BOOK OPERATIONS ====================
    @staticmethod
    def get_all_books():
        """Get all books with availability status"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, 
                       CASE WHEN b.available_copies > 0 THEN 'Available' ELSE 'Borrowed' END as status_text
                FROM books b
                ORDER BY b.id DESC
            """)
            return dictfetchall(cursor)
    
    @staticmethod
    def search_books(search_term):
        """Search books by title, author, or book code"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM books 
                WHERE title LIKE %s OR author LIKE %s OR book_code LIKE %s OR category LIKE %s
                ORDER BY title
            """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            return dictfetchall(cursor)
    
    @staticmethod
    def add_book(book_data, added_by):
        """Add new book (librarian only)"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO books (book_code, title, author, publisher, isbn, category, 
                                     edition, year_of_publication, total_copies, available_copies, 
                                     location, added_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    book_data['book_code'], book_data['title'], book_data['author'],
                    book_data.get('publisher'), book_data.get('isbn'), book_data.get('category'),
                    book_data.get('edition'), book_data.get('year_of_publication'),
                    book_data['total_copies'], book_data['total_copies'],
                    book_data.get('location'), added_by
                ))
                conn.commit()
                return True, "Book added successfully"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    @staticmethod
    def update_book(book_id, book_data):
        """Update book details"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE books 
                    SET title=%s, author=%s, publisher=%s, isbn=%s, category=%s,
                        edition=%s, year_of_publication=%s, total_copies=%s, 
                        available_copies=%s, location=%s
                    WHERE id=%s
                """, (
                    book_data['title'], book_data['author'], book_data.get('publisher'),
                    book_data.get('isbn'), book_data.get('category'), book_data.get('edition'),
                    book_data.get('year_of_publication'), book_data['total_copies'],
                    book_data['available_copies'], book_data.get('location'), book_id
                ))
                conn.commit()
                return True, "Book updated successfully"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    @staticmethod
    def delete_book(book_id):
        """Delete book (admin only)"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
                conn.commit()
                return True, "Book deleted successfully"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    # ==================== STUDENT OPERATIONS ====================
    @staticmethod
    def get_all_students():
        """Get all registered students"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.full_name, u.email, u.phone, u.is_active,
                       s.student_id, s.department, s.semester, s.total_books_borrowed,
                       s.current_books_borrowed, s.fine_amount, s.max_books_limit
                FROM users u
                JOIN students s ON u.id = s.user_id
                WHERE u.role = 'student'
                ORDER BY u.full_name
            """)
            return dictfetchall(cursor)
    
    @staticmethod
    def get_student_by_user_id(user_id):
        """Get student details by user ID"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.full_name, u.email, u.phone, u.is_active,
                       s.student_id, s.department, s.semester, s.year_of_study,
                       s.current_books_borrowed, s.total_books_borrowed, 
                       s.max_books_limit, s.fine_amount
                FROM users u
                JOIN students s ON u.id = s.user_id
                WHERE u.id = %s
            """, (user_id,))
            return dictfetchone(cursor)
    
    @staticmethod
    def get_student_by_student_id(student_id):
        """Get student by student ID"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, s.student_id, s.department, s.semester, s.current_books_borrowed,
                       s.max_books_limit, s.fine_amount
                FROM users u
                JOIN students s ON u.id = s.user_id
                WHERE s.student_id = %s
            """, (student_id,))
            return dictfetchone(cursor)
    
    @staticmethod
    def update_student_status(student_id, is_active):
        """Activate/Deactivate student account"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE users 
                    SET is_active = %s 
                    WHERE id = (SELECT user_id FROM students WHERE student_id = %s)
                """, (is_active, student_id))
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                return False
    
    # ==================== BORROWING OPERATIONS ====================
    @staticmethod
    def can_borrow_book(student_id):
        """Check if student can borrow more books"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_books_borrowed, max_books_limit, fine_amount 
                FROM students 
                WHERE student_id = %s
            """, (student_id,))
            student = dictfetchone(cursor)
            
            if not student:
                return False, "Student not found"
            
            if student.get('fine_amount', 0) > 0:
                return False, f"Please clear fine of ${student['fine_amount']}"
            
            current_borrowed = student.get('current_books_borrowed', 0)
            max_limit = student.get('max_books_limit', 5)
            
            if current_borrowed >= max_limit:
                return False, f"Maximum borrowing limit reached ({max_limit} books). You currently have {current_borrowed} books."
            
            remaining = max_limit - current_borrowed
            return True, f"You can borrow {remaining} more book(s)"
    
    @staticmethod
    def borrow_book(book_id, student_id, librarian_id, days=14):
        """Process book borrowing"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Check book availability
                cursor.execute("SELECT available_copies FROM books WHERE id = %s", (book_id,))
                book = cursor.fetchone()
                
                if not book or book[0] <= 0:
                    return False, "Book not available"
                
                # Check if student can borrow
                can_borrow, message = LibraryDB.can_borrow_book(student_id)
                if not can_borrow:
                    return False, message
                
                # Get student's database ID
                cursor.execute("SELECT id FROM students WHERE student_id = %s", (student_id,))
                student_result = cursor.fetchone()
                
                if not student_result:
                    return False, "Student record not found"
                
                student_db_id = student_result[0]
                
                # Generate borrowing code
                borrowing_code = f"BR{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
                borrow_date = date.today()
                due_date = borrow_date + timedelta(days=days)
                
                # Create borrowing record
                cursor.execute("""
                    INSERT INTO borrowings (borrowing_code, book_id, student_id, borrowed_by, 
                                           borrow_date, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'borrowed')
                """, (borrowing_code, book_id, student_db_id, librarian_id, borrow_date, due_date))
                
                # Update book available copies
                cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = %s", (book_id,))
                
                # Update student's borrowing counts
                cursor.execute("""
                    UPDATE students 
                    SET current_books_borrowed = current_books_borrowed + 1,
                        total_books_borrowed = total_books_borrowed + 1
                    WHERE student_id = %s
                """, (student_id,))
                
                conn.commit()
                return True, f"Book borrowed successfully. Due date: {due_date}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    @staticmethod
    def return_book(borrowing_id, librarian_id):
        """Process book return"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get borrowing details
                cursor.execute("""
                    SELECT b.id, b.book_id, b.student_id, b.due_date, b.status, s.student_id as student_identifier
                    FROM borrowings b
                    JOIN students s ON b.student_id = s.id
                    WHERE b.id = %s
                """, (borrowing_id,))
                borrowing = cursor.fetchone()
                
                if not borrowing:
                    return False, "Borrowing record not found"
                
                borrow_id, book_id, student_db_id, due_date, status, student_identifier = borrowing
                
                if status == 'returned':
                    return False, "Book already returned"
                
                # Calculate fine if overdue
                return_date = date.today()
                fine = 0
                if return_date > due_date:
                    days_overdue = (return_date - due_date).days
                    fine = days_overdue * 0.50
                
                # Update borrowing record
                cursor.execute("""
                    UPDATE borrowings 
                    SET return_date = %s, status = 'returned', 
                        fine_amount = %s, returned_to = %s
                    WHERE id = %s
                """, (return_date, fine, librarian_id, borrow_id))
                
                # Update book available copies
                cursor.execute("""
                    UPDATE books 
                    SET available_copies = available_copies + 1 
                    WHERE id = %s
                """, (book_id,))
                
                # Update student's current borrowed count
                cursor.execute("""
                    UPDATE students 
                    SET current_books_borrowed = current_books_borrowed - 1
                    WHERE id = %s
                """, (student_db_id,))
                
                # Update fine if any
                if fine > 0:
                    cursor.execute("""
                        UPDATE students 
                        SET fine_amount = fine_amount + %s
                        WHERE id = %s
                    """, (fine, student_db_id))
                
                conn.commit()
                return True, f"Book returned successfully. Fine: ${fine}"
            except Exception as e:
                conn.rollback()
                return False, str(e)
    
    @staticmethod
    def get_borrowings(status=None):
        """Get all borrowings with filters"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT br.id, br.borrowing_code, br.book_id, br.student_id, 
                       br.borrowed_by, br.borrow_date, br.due_date, br.return_date, 
                       br.status, br.fine_amount, br.remarks, br.created_at,
                       b.title as book_title, b.book_code
                FROM borrowings br
                JOIN books b ON br.book_id = b.id
            """
            
            if status:
                query += f" WHERE br.status = '{status}'"
            
            query += " ORDER BY br.borrow_date DESC"
            
            cursor.execute(query)
            return dictfetchall(cursor)
    
    @staticmethod
    def get_student_borrowings(student_id):
        """Get borrowing history of specific student"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    br.id,
                    br.borrowing_code,
                    br.borrow_date,
                    br.due_date,
                    br.return_date,
                    br.status,
                    br.fine_amount,
                    b.title as book_title,
                    b.book_code,
                    b.author
                FROM borrowings br
                JOIN books b ON br.book_id = b.id
                JOIN students s ON br.student_id = s.id
                WHERE s.student_id = %s
                ORDER BY br.borrow_date DESC
            """, (student_id,))
            
            rows = cursor.fetchall()
            history = []
            for row in rows:
                history.append({
                    'id': row[0],
                    'borrowing_code': row[1],
                    'borrow_date': str(row[2]) if row[2] else None,
                    'due_date': str(row[3]) if row[3] else None,
                    'return_date': str(row[4]) if row[4] else None,
                    'status': row[5],
                    'fine_amount': float(row[6]) if row[6] else 0,
                    'book_title': row[7],
                    'book_code': row[8],
                    'author': row[9]
                })
            return history
    
    @staticmethod
    def get_dashboard_stats():
        """Get dashboard statistics"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            stats = {}
            
            cursor.execute("SELECT COUNT(*) FROM books")
            stats['total_books'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(available_copies) FROM books")
            result = cursor.fetchone()[0]
            stats['available_books'] = result or 0
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
            stats['total_students'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM borrowings WHERE status = 'borrowed'")
            stats['borrowed_books'] = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM borrowings 
                WHERE status = 'borrowed' AND due_date < CURDATE()
            """)
            stats['overdue_books'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'librarian'")
            stats['total_librarians'] = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM borrowings 
                WHERE DATE(borrow_date) = CURDATE()
            """)
            stats['today_borrowings'] = cursor.fetchone()[0] or 0
            
            return stats
    
    @staticmethod
    def get_all_users():
        """Get all users (admin only)"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.password, u.email, u.full_name, u.phone, 
                       u.role, u.is_active, u.created_at, u.last_login,
                       s.student_id, s.department, s.semester, s.year_of_study,
                       s.current_books_borrowed, s.total_books_borrowed
                FROM users u
                LEFT JOIN students s ON u.id = s.user_id
                ORDER BY u.created_at DESC
            """)
            return dictfetchall(cursor)
    
    @staticmethod
    def log_activity(user_id, action, table_name, record_id, details):
        """Log user activities"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, table_name, record_id, details)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, action, table_name, record_id, details))
            conn.commit()
    
    @staticmethod
    def get_audit_logs():
        """Get all activity logs (admin only)"""
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT al.*, u.username, u.full_name
                FROM audit_logs al
                JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT 100
            """)
            return dictfetchall(cursor)