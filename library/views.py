# library/views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, date
import json
from .db_operations import LibraryDB
from .db_config import Database

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

def get_logged_in_user(request):
    """Get currently logged in user from session"""
    return request.session.get('user')

def login_required(view_func):
    """Decorator to check if user is logged in"""
    def wrapper(request, *args, **kwargs):
        if not get_logged_in_user(request):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def role_required(*roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            user = get_logged_in_user(request)
            if not user or user['role'] not in roles:
                return render(request, 'access_denied.html', {
                    'message': 'You do not have permission to access this page.'
                })
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# ==================== AUTHENTICATION VIEWS ====================
def login_view(request):
    """Handle user login for all roles"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = LibraryDB.authenticate_user(username, password)
        
        if user:
            request.session['user'] = user
            request.session['user_id'] = user['id']
            request.session['role'] = user['role']
            request.session['username'] = user['username']
            
            LibraryDB.log_activity(
                user['id'], 
                'LOGIN', 
                'users', 
                user['id'], 
                f'User {username} logged in'
            )
            
            if user['role'] == 'admin':
                return redirect('admin_dashboard')
            elif user['role'] == 'librarian':
                return redirect('librarian_dashboard')
            elif user['role'] == 'student':
                return redirect('student_dashboard')
            else:
                return redirect('login')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    
    return render(request, 'login.html')

def logout_view(request):
    """Handle user logout"""
    user = get_logged_in_user(request)
    if user:
        LibraryDB.log_activity(
            user['id'], 
            'LOGOUT', 
            'users', 
            user['id'], 
            f'User {user["username"]} logged out'
        )
    request.session.flush()
    return redirect('login')

def register_view(request):
    """Student registration"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        student_id = request.POST.get('student_id')
        department = request.POST.get('department')
        semester = request.POST.get('semester')
        
        if password != confirm_password:
            return render(request, 'register.html', {'error': 'Passwords do not match'})
        
        success, message = LibraryDB.register_student(
            username, password, email, full_name, phone, 
            student_id, department, semester
        )
        
        if success:
            return render(request, 'login.html', {'message': 'Registration successful! Please login.'})
        else:
            return render(request, 'register.html', {'error': message})
    
    return render(request, 'register.html')

@login_required
def change_password(request):
    """Change password for logged in user"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        user = get_logged_in_user(request)
        
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM users WHERE id = %s", (user['id'],))
            db_password = cursor.fetchone()
            
            if db_password and db_password[0] != current_password:
                return JsonResponse({'success': False, 'message': 'Current password is incorrect'})
            
            if new_password != confirm_password:
                return JsonResponse({'success': False, 'message': 'New passwords do not match'})
            
            if len(new_password) < 4:
                return JsonResponse({'success': False, 'message': 'Password must be at least 4 characters'})
            
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, user['id']))
            conn.commit()
            
            LibraryDB.log_activity(
                user['id'],
                'CHANGE_PASSWORD',
                'users',
                user['id'],
                'Password changed'
            )
        
        return JsonResponse({'success': True, 'message': 'Password changed successfully'})
    
    return render(request, 'change_password.html')

# ==================== STUDENT VIEWS ====================
@login_required
@role_required('student')
def student_dashboard(request):
    """Student dashboard showing their borrowing status"""
    user = get_logged_in_user(request)
    student = LibraryDB.get_student_by_user_id(user['id'])
    
    if not student:
        return render(request, 'error.html', {'message': 'Student profile not found'})
    
    current_borrowings = LibraryDB.get_student_borrowings(student['student_id'])
    active_borrowings = [b for b in current_borrowings if b['status'] in ['borrowed', 'overdue']]
    borrowing_history = [b for b in current_borrowings if b['status'] == 'returned']
    
    # Keep dashboard stats consistent with actual borrowings
    student['current_books_borrowed'] = len(active_borrowings)
    student['total_books_borrowed'] = len(current_borrowings)
    
    context = {
        'user': user,
        'student': student,
        'active_borrowings': active_borrowings,
        'borrowing_history': borrowing_history[:10],
        'total_active': len(active_borrowings),
        'total_history': len(borrowing_history),
        'today': date.today()
    }
    return render(request, 'student/dashboard.html', context)

@login_required
@role_required('student')
def student_books(request):
    """View all available books"""
    books = LibraryDB.get_all_books()
    return render(request, 'student/books.html', {'books': books})

@login_required
@role_required('student')
def student_borrow(request):
    """Student borrow a book"""
    user = get_logged_in_user(request)
    student = LibraryDB.get_student_by_user_id(user['id'])
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        
        can_borrow, message = LibraryDB.can_borrow_book(student['student_id'])
        if not can_borrow:
            return JsonResponse({'success': False, 'message': message})
        
        success, message = LibraryDB.borrow_book(book_id, student['student_id'], None, 14)
        
        if success:
            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'message': message})
    
    # Recalculate borrowing stats from current borrowings so the page is always accurate
    current_borrowings = LibraryDB.get_student_borrowings(student['student_id'])
    active_borrowings = [b for b in current_borrowings if b['status'] in ['borrowed', 'overdue']]
    student['current_books_borrowed'] = len(active_borrowings)
    student['total_books_borrowed'] = len(current_borrowings)
    
    books = LibraryDB.get_all_books()
    available_books = [b for b in books if b['available_copies'] > 0]
    
    context = {
        'books': available_books,
        'student': student
    }
    return render(request, 'student/borrow.html', context)

@login_required
@role_required('student')
def student_history(request):
    """Student borrowing history"""
    from datetime import datetime
    
    user = get_logged_in_user(request)
    student = LibraryDB.get_student_by_user_id(user['id'])
    history = LibraryDB.get_student_borrowings(student['student_id'])
    
    # Process each item to convert dates and calculate status
    today = date.today()
    for item in history:
        # Convert due_date string to date object if needed
        if item.get('due_date'):
            if isinstance(item['due_date'], str):
                due_date = datetime.strptime(item['due_date'], '%Y-%m-%d').date()
            else:
                due_date = item['due_date']
            item['due_date_obj'] = due_date
            
            # Calculate status based on due date
            if item['status'] == 'borrowed' and due_date < today:
                item['status'] = 'overdue'
                days_overdue = (today - due_date).days
                item['days_overdue'] = days_overdue
                item['fine_amount'] = days_overdue * 0.50
        
        # Convert other dates to string for display
        if item.get('borrow_date') and isinstance(item['borrow_date'], date):
            item['borrow_date'] = str(item['borrow_date'])
        if item.get('due_date') and isinstance(item['due_date'], date):
            item['due_date'] = str(item['due_date'])
        if item.get('return_date') and isinstance(item['return_date'], date):
            item['return_date'] = str(item['return_date'])
    
    # Calculate statistics
    total_borrowed = len(history)
    currently_borrowed = len([h for h in history if h['status'] in ['borrowed', 'overdue']])
    returned_books = len([h for h in history if h['status'] == 'returned'])
    total_fines = sum([float(h.get('fine_amount', 0)) for h in history])
    
    context = {
        'history': history,
        'total_borrowed': total_borrowed,
        'currently_borrowed': currently_borrowed,
        'returned_books': returned_books,
        'total_fines': total_fines,
        'user': user,
        'student': student,
        'today': today
    }
    return render(request, 'student/history.html', context)

@login_required
@role_required('student')
def student_profile(request):
    """Student profile view and edit"""
    user = get_logged_in_user(request)
    student = LibraryDB.get_student_by_user_id(user['id'])
    
    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            department = request.POST.get('department')
            semester = request.POST.get('semester')
            year_of_study = request.POST.get('year_of_study')
            
            # Debug print
            print(f"Updating profile for user {user['id']}")
            print(f"Full Name: {full_name}, Email: {email}, Phone: {phone}")
            print(f"Department: {department}, Semester: {semester}, Year: {year_of_study}")
            
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update users table
                cursor.execute("""
                    UPDATE users 
                    SET full_name = %s, email = %s, phone = %s 
                    WHERE id = %s
                """, (full_name, email, phone, user['id']))
                
                # Update students table
                cursor.execute("""
                    UPDATE students 
                    SET department = %s, semester = %s, year_of_study = %s
                    WHERE user_id = %s
                """, (department, semester, year_of_study, user['id']))
                
                conn.commit()
                
                # Update session user data
                user['full_name'] = full_name
                user['email'] = email
                request.session['user'] = user
                
                return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
                
        except Exception as e:
            print(f"Error updating profile: {e}")
            return JsonResponse({'success': False, 'message': str(e)})
    
    context = {
        'user': user,
        'student': student
    }
    return render(request, 'student/profile.html', context)
@login_required
@role_required('student')
@login_required
@role_required('student')
def student_return(request):
    """Student return a book"""
    from datetime import datetime
    
    user = get_logged_in_user(request)
    student = LibraryDB.get_student_by_user_id(user['id'])
    
    # Get current borrowings for display
    current_borrowings = LibraryDB.get_student_borrowings(student['student_id'])
    borrowed_books = [b for b in current_borrowings if b['status'] in ['borrowed', 'overdue']]
    
    # Process each book to calculate fine and days properly
    today = date.today()
    for book in borrowed_books:
        # Convert due_date string to date object for comparison
        if isinstance(book['due_date'], str):
            book['due_date_obj'] = datetime.strptime(book['due_date'], '%Y-%m-%d').date()
        else:
            book['due_date_obj'] = book['due_date']
        
        # Calculate days left or overdue
        if book['due_date_obj'] < today:
            book['status'] = 'overdue'
            days_overdue = (today - book['due_date_obj']).days
            book['days_overdue'] = days_overdue
            book['fine_amount'] = days_overdue * 0.50
            book['days_left'] = 0
        else:
            book['status'] = 'borrowed'
            book['days_left'] = (book['due_date_obj'] - today).days
            book['days_overdue'] = 0
            if 'fine_amount' not in book:
                book['fine_amount'] = 0
    
    # Calculate statistics
    currently_borrowed = len(borrowed_books)
    overdue_books = len([b for b in borrowed_books if b.get('status') == 'overdue'])
    total_fines = sum([float(b.get('fine_amount', 0)) for b in borrowed_books])
    
    if request.method == 'POST':
        borrow_id = request.POST.get('borrow_id')
        
        # Process the return
        success, message = LibraryDB.return_book(borrow_id, user['id'])
        
        if success:
            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'message': message})
    
    context = {
        'borrowed_books': borrowed_books,
        'currently_borrowed': currently_borrowed,
        'overdue_books': overdue_books,
        'total_fines': total_fines,
        'user': user,
        'student': student
    }
    return render(request, 'student/return.html', context)
# ==================== LIBRARIAN VIEWS ====================
@login_required
@role_required('librarian', 'admin')
@login_required
@role_required('librarian', 'admin')
@login_required
@role_required('librarian', 'admin')
def librarian_dashboard(request):
    """Librarian dashboard with statistics"""
    stats = LibraryDB.get_dashboard_stats()
    
    # Get currently borrowed books
    borrowed_books = LibraryDB.get_borrowings('borrowed')
    if not borrowed_books:
        borrowed_books = []
    
    # Get returned books (last 10)
    returned_books = LibraryDB.get_borrowings('returned')
    if returned_books:
        returned_books = returned_books[:10]
    else:
        returned_books = []
    
    # Add student names and book titles to borrowed books
    for borrowing in borrowed_books:
        try:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.full_name, b.title
                    FROM students s
                    JOIN users u ON s.user_id = u.id
                    JOIN books b ON b.id = %s
                    WHERE s.id = %s
                """, (borrowing.get('book_id'), borrowing.get('student_id')))
                row = cursor.fetchone()
                if row:
                    borrowing['student_name'] = row[0]
                    borrowing['book_title'] = row[1]
                else:
                    borrowing['student_name'] = 'Unknown'
                    borrowing['book_title'] = 'Unknown'
        except Exception as e:
            borrowing['student_name'] = 'Unknown'
            borrowing['book_title'] = 'Unknown'
    
    # Add student names and book titles to returned books
    for borrowing in returned_books:
        try:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.full_name, b.title
                    FROM students s
                    JOIN users u ON s.user_id = u.id
                    JOIN books b ON b.id = %s
                    WHERE s.id = %s
                """, (borrowing.get('book_id'), borrowing.get('student_id')))
                row = cursor.fetchone()
                if row:
                    borrowing['student_name'] = row[0]
                    borrowing['book_title'] = row[1]
                    # Calculate days borrowed
                    if borrowing.get('borrow_date') and borrowing.get('return_date'):
                        days = (borrowing['return_date'] - borrowing['borrow_date']).days
                        borrowing['days_borrowed'] = days
                else:
                    borrowing['student_name'] = 'Unknown'
                    borrowing['book_title'] = 'Unknown'
        except Exception as e:
            borrowing['student_name'] = 'Unknown'
            borrowing['book_title'] = 'Unknown'
    
    # Get overdue books
    overdue_books = []
    for borrowing in borrowed_books:
        due_date = borrowing.get('due_date')
        if due_date and isinstance(due_date, date) and due_date < date.today():
            days_overdue = (date.today() - due_date).days
            borrowing['days_overdue'] = days_overdue
            borrowing['fine_amount'] = days_overdue * 0.50
            overdue_books.append(borrowing)
    
    # Get counts for stats
    today_returns = len([b for b in returned_books if b.get('return_date') == date.today()]) if returned_books else 0
    
    # Update stats with returned books count
    stats['returned_books_today'] = today_returns
    
    # Get available books count
    available_books_count = 0
    low_stock_books = []
    popular_books = []
    
    try:
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get available books count
            cursor.execute("SELECT COUNT(*) FROM books WHERE available_copies > 0")
            result = cursor.fetchone()
            available_books_count = result[0] if result else 0
            
            # Get low stock books
            cursor.execute("""
                SELECT id, book_code, title, available_copies, total_copies 
                FROM books 
                WHERE available_copies < 3 AND available_copies > 0 
                LIMIT 10
            """)
            low_rows = cursor.fetchall()
            for row in low_rows:
                low_stock_books.append({
                    'id': row[0],
                    'book_code': row[1],
                    'title': row[2],
                    'available_copies': row[3],
                    'total_copies': row[4]
                })
            
            # Get popular books this month
            cursor.execute("""
                SELECT b.title, b.author, COUNT(br.id) as borrow_count
                FROM books b
                JOIN borrowings br ON b.id = br.book_id
                WHERE MONTH(br.borrow_date) = MONTH(CURDATE())
                  AND YEAR(br.borrow_date) = YEAR(CURDATE())
                GROUP BY b.id
                ORDER BY borrow_count DESC
                LIMIT 5
            """)
            popular_rows = cursor.fetchall()
            for row in popular_rows:
                popular_books.append({
                    'title': row[0],
                    'author': row[1],
                    'borrow_count': row[2]
                })
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
    
    context = {
        'stats': stats,
        'borrowed_books': borrowed_books[:10],
        'returned_books': returned_books,
        'overdue_books': overdue_books[:5],
        'available_books_count': available_books_count,
        'low_stock_books': low_stock_books,
        'popular_books': popular_books,
        'user': get_logged_in_user(request),
        'today': date.today()
    }
    return render(request, 'librarian/dashboard.html', context)

@login_required
@role_required('librarian', 'admin')
def manage_books(request):
    """Manage all books (CRUD operations)"""
    books = LibraryDB.get_all_books()
    return render(request, 'librarian/books.html', {'books': books})

@login_required
@role_required('librarian', 'admin')
def add_book(request):
    """Add new book to library"""
    if request.method == 'POST':
        book_data = {
            'book_code': request.POST.get('book_code'),
            'title': request.POST.get('title'),
            'author': request.POST.get('author'),
            'publisher': request.POST.get('publisher'),
            'isbn': request.POST.get('isbn'),
            'category': request.POST.get('category'),
            'edition': request.POST.get('edition'),
            'year_of_publication': request.POST.get('year_of_publication'),
            'total_copies': int(request.POST.get('total_copies')),
            'location': request.POST.get('location')
        }
        
        success, message = LibraryDB.add_book(book_data, request.session['user_id'])
        
        if success:
            return redirect('manage_books')
        else:
            return render(request, 'librarian/add_book.html', {'error': message})
    
    return render(request, 'librarian/add_book.html')

@login_required
@role_required('librarian', 'admin')
def edit_book(request, book_id):
    """Edit book details"""
    if request.method == 'POST':
        book_data = {
            'title': request.POST.get('title'),
            'author': request.POST.get('author'),
            'publisher': request.POST.get('publisher'),
            'isbn': request.POST.get('isbn'),
            'category': request.POST.get('category'),
            'edition': request.POST.get('edition'),
            'year_of_publication': request.POST.get('year_of_publication'),
            'total_copies': int(request.POST.get('total_copies')),
            'available_copies': int(request.POST.get('available_copies')),
            'location': request.POST.get('location')
        }
        
        success, message = LibraryDB.update_book(book_id, book_data)
        
        if success:
            return redirect('manage_books')
        else:
            return render(request, 'librarian/edit_book.html', {'error': message, 'book_id': book_id})
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
        row = cursor.fetchone()
        if row:
            book = {
                'id': row[0],
                'book_code': row[1],
                'title': row[2],
                'author': row[3],
                'publisher': row[4],
                'isbn': row[5],
                'category': row[6],
                'edition': row[7],
                'year_of_publication': row[8],
                'total_copies': row[9],
                'available_copies': row[10],
                'location': row[11]
            }
        else:
            book = None
    
    return render(request, 'librarian/edit_book.html', {'book': book})

@login_required
@role_required('librarian', 'admin')
def delete_book(request, book_id):
    """Delete a book (only if not borrowed)"""
    if request.method == 'POST':
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM borrowings 
                WHERE book_id = %s AND status = 'borrowed'
            """, (book_id,))
            result = cursor.fetchone()
            
            if result[0] > 0:
                return JsonResponse({'success': False, 'message': 'Cannot delete: Book is currently borrowed'})
        
        success, message = LibraryDB.delete_book(book_id)
        return JsonResponse({'success': success, 'message': message})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
@role_required('librarian', 'admin')
def get_book_json(request, book_id):
    """Return book data as JSON for AJAX"""
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
        row = cursor.fetchone()
        
        if row:
            book = {
                'id': row[0],
                'book_code': row[1],
                'title': row[2],
                'author': row[3],
                'publisher': row[4],
                'isbn': row[5],
                'category': row[6],
                'edition': row[7],
                'year_of_publication': row[8],
                'total_copies': row[9],
                'available_copies': row[10],
                'location': row[11],
                'added_date': str(row[13]) if len(row) > 13 else None
            }
            return JsonResponse({'success': True, 'book': book})
    
    return JsonResponse({'success': False, 'message': 'Book not found'})

@login_required
@role_required('librarian', 'admin')
def manage_students(request):
    """Manage all students"""
    students = LibraryDB.get_all_students()
    
    total_students = len(students)
    active_students = len([s for s in students if s.get('is_active')])
    students_with_borrowings = len([s for s in students if s.get('total_books_borrowed', 0) > 0])
    total_books_borrowed = sum([s.get('total_books_borrowed', 0) for s in students])
    
    context = {
        'students': students,
        'total_students': total_students,
        'active_students': active_students,
        'students_with_borrowings': students_with_borrowings,
        'total_books_borrowed': total_books_borrowed,
        'user': get_logged_in_user(request)
    }
    return render(request, 'librarian/students.html', context)

@login_required
@role_required('librarian', 'admin')
def get_student_json(request, user_id):
    """Get student data as JSON"""
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.full_name, u.email, u.phone, u.is_active, u.created_at,
                   s.student_id, s.department, s.semester, s.current_books_borrowed, 
                   s.total_books_borrowed, s.max_books_limit, s.fine_amount
            FROM users u
            JOIN students s ON u.id = s.user_id
            WHERE u.id = %s
        """, (user_id,))
        row = cursor.fetchone()
        
        if row:
            student = {
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'phone': row[4],
                'is_active': bool(row[5]),
                'created_at': str(row[6]) if row[6] else None,
                'student_id': row[7],
                'department': row[8],
                'semester': row[9],
                'current_books_borrowed': row[10],
                'total_books_borrowed': row[11],
                'max_books_limit': row[12],
                'fine_amount': float(row[13]) if row[13] else 0
            }
            return JsonResponse({'success': True, 'student': student})
    
    return JsonResponse({'success': False, 'message': 'Student not found'})

@login_required
@role_required('librarian', 'admin')
def get_student_history_json(request, student_id):
    """Get student borrowing history as JSON"""
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT br.id, br.borrowing_code, br.borrow_date, br.due_date, br.return_date, 
                   br.status, br.fine_amount, b.title as book_title
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            JOIN students s ON br.student_id = s.id
            WHERE s.student_id = %s
            ORDER BY br.borrow_date DESC
        """, (student_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'id': row[0],
                'borrowing_code': row[1],
                'borrow_date': str(row[2]) if row[2] else None,
                'due_date': str(row[3]) if row[3] else None,
                'return_date': str(row[4]) if row[4] else None,
                'status': row[5],
                'fine_amount': float(row[6]) if row[6] else 0,
                'book_title': row[7]
            })
        
        return JsonResponse({'success': True, 'history': history})

@login_required
@role_required('librarian', 'admin')
def toggle_student_status(request):
    """Activate/deactivate student"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        is_active = action == 'activate'
        
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (is_active, user_id))
            conn.commit()
            
            LibraryDB.log_activity(
                request.session.get('user_id'),
                f'{action.upper()}_STUDENT',
                'users',
                user_id,
                f'Student {user_id} {action}d'
            )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
@role_required('librarian', 'admin')
def update_student(request):
    """Update student information"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        department = request.POST.get('department')
        semester = request.POST.get('semester')
        max_books_limit = request.POST.get('max_books_limit')
        
        try:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET full_name = %s, email = %s, phone = %s 
                    WHERE id = %s
                """, (full_name, email, phone, user_id))
                
                cursor.execute("""
                    UPDATE students 
                    SET department = %s, semester = %s, max_books_limit = %s
                    WHERE user_id = %s
                """, (department, semester, max_books_limit, user_id))
                
                conn.commit()
                
                LibraryDB.log_activity(
                    request.session.get('user_id'),
                    'UPDATE_STUDENT',
                    'users',
                    user_id,
                    f'Updated student {full_name}'
                )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False})

@login_required
@role_required('librarian', 'admin')
def student_detail(request, student_id):
    """View student details with borrowing history"""
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.full_name, u.email, u.phone, u.is_active, u.created_at,
                   s.student_id, s.department, s.semester, s.current_books_borrowed, 
                   s.total_books_borrowed, s.max_books_limit, s.fine_amount
            FROM users u
            JOIN students s ON u.id = s.user_id
            WHERE s.student_id = %s
        """, (student_id,))
        row = cursor.fetchone()
        
        if not row:
            return render(request, 'error.html', {'message': 'Student not found'})
        
        student = {
            'id': row[0],
            'full_name': row[1],
            'email': row[2],
            'phone': row[3],
            'is_active': bool(row[4]),
            'created_at': row[5],
            'student_id': row[6],
            'department': row[7],
            'semester': row[8],
            'current_books_borrowed': row[9],
            'total_books_borrowed': row[10],
            'max_books_limit': row[11],
            'fine_amount': float(row[12]) if row[12] else 0
        }
        
        cursor.execute("""
            SELECT br.*, b.title as book_title
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            WHERE br.student_id = (SELECT id FROM students WHERE student_id = %s)
            AND br.status IN ('borrowed', 'overdue')
        """, (student_id,))
        
        active_borrowings = []
        for r in cursor.fetchall():
            due_date = r[5]
            days_left = (due_date - date.today()).days
            borrowing = {
                'book_title': r[12],
                'borrow_date': str(r[4]),
                'due_date': str(due_date),
                'status': 'overdue' if days_left < 0 else 'borrowed',
                'days_left': abs(days_left) if days_left < 0 else days_left
            }
            active_borrowings.append(borrowing)
        
        cursor.execute("""
            SELECT br.*, b.title as book_title
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            WHERE br.student_id = (SELECT id FROM students WHERE student_id = %s)
            AND br.status = 'returned'
            ORDER BY br.return_date DESC
            LIMIT 10
        """, (student_id,))
        
        returned_books = []
        for r in cursor.fetchall():
            returned_books.append({
                'book_title': r[12],
                'borrow_date': str(r[4]),
                'due_date': str(r[5]),
                'return_date': str(r[6]) if r[6] else None,
                'fine_amount': float(r[8]) if r[8] else 0
            })
    
    context = {
        'student': student,
        'active_borrowings': active_borrowings,
        'returned_books': returned_books,
        'user': get_logged_in_user(request)
    }
    return render(request, 'librarian/student_detail.html', context)

@login_required
@role_required('librarian', 'admin')
def process_borrow(request):
    """Librarian processes book borrowing"""
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        student_id = request.POST.get('student_id')
        days = int(request.POST.get('days', 14))
        
        success, message = LibraryDB.borrow_book(
            book_id, student_id, request.session['user_id'], days
        )
        
        if success:
            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'message': message})
    
    books = LibraryDB.get_all_books()
    available_books = [b for b in books if b['available_copies'] > 0]
    students = LibraryDB.get_all_students()
    active_students = [s for s in students if s.get('is_active')]
    
    context = {
        'books': available_books,
        'students': active_students
    }
    return render(request, 'librarian/borrow.html', context)

@login_required
@role_required('librarian', 'admin')
def process_return(request):
    """Librarian processes book return"""
    if request.method == 'POST':
        borrowing_id = request.POST.get('borrowing_id')
        success, message = LibraryDB.return_book(borrowing_id, request.session['user_id'])
        
        if success:
            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'message': message})
    
    borrowings = LibraryDB.get_borrowings('borrowed')
    
    if borrowings:
        for borrowing in borrowings:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.student_id, u.full_name as student_name, b.title, b.book_code
                    FROM borrowings br
                    JOIN students s ON br.student_id = s.id
                    JOIN users u ON s.user_id = u.id
                    JOIN books b ON br.book_id = b.id
                    WHERE br.id = %s
                """, (borrowing.get('id'),))
                details = cursor.fetchone()
                if details:
                    borrowing['student_id_num'] = details[0]
                    borrowing['student_name'] = details[1]
                    borrowing['book_title'] = details[2]
                    borrowing['book_code'] = details[3]
    
    return render(request, 'librarian/return.html', {'borrowings': borrowings or []})

@login_required
@role_required('librarian', 'admin')
def all_borrowings(request):
    """View all borrowing transactions"""
    user = get_logged_in_user(request)
    borrowings = LibraryDB.get_borrowings()
    all_borrowings = borrowings or []
    
    if all_borrowings:
        today = date.today()
        for borrowing in all_borrowings:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.full_name as student_name, s.student_id
                    FROM students s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.id = %s
                """, (borrowing.get('student_id'),))
                student = cursor.fetchone()
                if student:
                    borrowing['student_name'] = student[0]
                    borrowing['student_id_num'] = student[1]

            # Mark overdue if a borrowed book is past its due date
            if borrowing.get('status') == 'borrowed' and borrowing.get('due_date') and borrowing['due_date'] < today:
                borrowing['status'] = 'overdue'
                borrowing['days_overdue'] = (today - borrowing['due_date']).days
                borrowing['fine_amount'] = float(borrowing['days_overdue'] * 0.50)
            else:
                borrowing.setdefault('days_overdue', 0)
                borrowing.setdefault('fine_amount', borrowing.get('fine_amount', 0))
    
    borrowed_count = len([b for b in all_borrowings if b.get('status') == 'borrowed'])
    returned_count = len([b for b in all_borrowings if b.get('status') == 'returned'])
    overdue_count = len([b for b in all_borrowings if b.get('status') == 'overdue'])
    
    status_filter = request.GET.get('status', 'all')
    borrowings = all_borrowings
    if status_filter != 'all':
        borrowings = [b for b in all_borrowings if b.get('status') == status_filter]
    
    context = {
        'user': user,
        'borrowings': borrowings,
        'all_borrowings_count': len(all_borrowings),
        'borrowed_count': borrowed_count,
        'returned_count': returned_count,
        'overdue_count': overdue_count,
        'status_filter': status_filter,
        'today': date.today()
    }
    return render(request, 'librarian/borrowings.html', context)

@login_required
@role_required('librarian', 'admin')
def search_books_librarian(request):
    """Search books (librarian view)"""
    query = request.GET.get('q', '')
    if query:
        books = LibraryDB.search_books(query)
    else:
        books = []
    return render(request, 'librarian/search_books.html', {'books': books, 'query': query})

@login_required
@role_required('librarian', 'admin')
def librarian_reports(request):
    """Generate various reports"""
    report_type = request.GET.get('type', 'borrowings')
    
    context = {'report_type': report_type}
    
    if report_type == 'borrowings':
        start_date = request.GET.get('start_date', str(date.today().replace(day=1)))
        end_date = request.GET.get('end_date', str(date.today()))
        
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) as returned,
                       SUM(CASE WHEN status = 'borrowed' THEN 1 ELSE 0 END) as borrowed,
                       SUM(fine_amount) as total_fines
                FROM borrowings
                WHERE borrow_date BETWEEN %s AND %s
            """, (start_date, end_date))
            row = cursor.fetchone()
            stats = {
                'total': row[0] if row else 0,
                'returned': row[1] if row else 0,
                'borrowed': row[2] if row else 0,
                'total_fines': float(row[3]) if row and row[3] else 0
            }
            
            cursor.execute("""
                SELECT b.title, COUNT(*) as borrow_count
                FROM borrowings br
                JOIN books b ON br.book_id = b.id
                WHERE br.borrow_date BETWEEN %s AND %s
                GROUP BY br.book_id
                ORDER BY borrow_count DESC
                LIMIT 10
            """, (start_date, end_date))
            popular_books = []
            for row in cursor.fetchall():
                popular_books.append({'title': row[0], 'borrow_count': row[1]})
        
        context.update({
            'stats': stats,
            'popular_books': popular_books,
            'start_date': start_date,
            'end_date': end_date
        })
    
    elif report_type == 'students':
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(s.department, 'Not Specified') as department, 
                       COUNT(*) as total_students,
                       COALESCE(SUM(s.total_books_borrowed), 0) as total_borrowed
                FROM students s
                GROUP BY s.department
            """)
            department_stats = []
            for row in cursor.fetchall():
                department_stats.append({
                    'department': row[0],
                    'total_students': row[1],
                    'total_borrowed': row[2]
                })
        
        context['department_stats'] = department_stats
    
    return render(request, 'librarian/reports.html', context)

# ==================== ADMIN/SUPERUSER VIEWS ====================
@login_required
@role_required('admin')
def admin_dashboard(request):
    """Superuser dashboard with full system control"""
    stats = LibraryDB.get_dashboard_stats()
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM borrowings")
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM borrowings WHERE status = 'returned'")
        total_returned = cursor.fetchone()[0]
        
        cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        role_rows = cursor.fetchall()
        role_stats = [{'role': r[0], 'count': r[1]} for r in role_rows]
        
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
        trend_rows = cursor.fetchall()
        activity_trend = [{'date': str(r[0]), 'count': r[1]} for r in trend_rows]
    
    users = LibraryDB.get_all_users()
    logs = LibraryDB.get_audit_logs()
    
    context = {
        'stats': stats,
        'total_users': total_users,
        'total_transactions': total_transactions,
        'total_returned': total_returned,
        'role_stats': role_stats,
        'activity_trend': activity_trend,
        'users': users[:10] if users else [],
        'logs': logs[:20] if logs else [],
        'user': get_logged_in_user(request)
    }
    return render(request, 'admin/dashboard.html', context)

@login_required
@role_required('admin')
def manage_users(request):
    """Superuser: Manage all users"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_librarian':
            username = request.POST.get('username')
            password = request.POST.get('password')
            email = request.POST.get('email')
            full_name = request.POST.get('full_name')
            phone = request.POST.get('phone')
            
            success, message = LibraryDB.add_librarian(username, password, email, full_name, phone)
            
            if success:
                return JsonResponse({'success': True, 'message': 'Librarian added successfully'})
            return JsonResponse({'success': False, 'message': message})
        
        elif action == 'toggle_user':
            user_id = request.POST.get('user_id')
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s AND role != 'admin'", (user_id,))
                conn.commit()
            return JsonResponse({'success': True})
        
        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = %s AND role != 'admin'", (user_id,))
                conn.commit()
            return JsonResponse({'success': True})
        
        elif action == 'reset_password':
            user_id = request.POST.get('user_id')
            new_password = request.POST.get('new_password')
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, user_id))
                conn.commit()
            return JsonResponse({'success': True})
    
    users = LibraryDB.get_all_users()
    return render(request, 'admin/manage_users.html', {'users': users})

@login_required
@role_required('admin')
def system_logs(request):
    """Superuser: View all system activities"""
    logs = LibraryDB.get_audit_logs()
    
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    
    if action_filter:
        logs = [log for log in logs if log.get('action') == action_filter]
    if user_filter:
        logs = [log for log in logs if str(log.get('user_id')) == user_filter]
    
    actions = list(set([log.get('action') for log in logs])) if logs else []
    users = LibraryDB.get_all_users()
    
    context = {
        'logs': logs,
        'actions': actions,
        'users': users,
        'action_filter': action_filter,
        'user_filter': user_filter
    }
    return render(request, 'admin/system_logs.html', context)

@login_required
@role_required('admin')
def backup_database(request):
    """Superuser: Backup database"""
    if request.method == 'POST':
        LibraryDB.log_activity(
            request.session['user_id'], 
            'BACKUP_DATABASE', 
            'system', 
            0, 
            'Database backup initiated'
        )
        return JsonResponse({'success': True, 'message': 'Backup completed successfully'})
    
    return render(request, 'admin/backup.html')

@login_required
@role_required('admin')
def system_settings(request):
    """Superuser: System configuration"""
    if request.method == 'POST':
        max_borrow_limit = request.POST.get('max_borrow_limit')
        fine_per_day = request.POST.get('fine_per_day')
        borrowing_days = request.POST.get('borrowing_days')
        
        LibraryDB.log_activity(
            request.session['user_id'],
            'UPDATE_SETTINGS',
            'system',
            0,
            f'Updated settings: Max={max_borrow_limit}, Fine={fine_per_day}, Days={borrowing_days}'
        )
        
        return JsonResponse({'success': True})
    
    settings = {
        'max_borrow_limit': 5,
        'fine_per_day': 0.50,
        'borrowing_days': 14
    }
    return render(request, 'admin/settings.html', {'settings': settings})

@login_required
@role_required('admin')
def system_stats(request):
    """Superuser: Detailed system statistics"""
    stats = LibraryDB.get_dashboard_stats()
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        daily_activity = [{'date': str(r[0]), 'count': r[1]} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT u.username, u.full_name, u.role, COUNT(*) as action_count
            FROM audit_logs al
            JOIN users u ON al.user_id = u.id
            WHERE al.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY al.user_id
            ORDER BY action_count DESC
            LIMIT 10
        """)
        active_users = [{'username': r[0], 'full_name': r[1], 'role': r[2], 'action_count': r[3]} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT b.title, b.author, COUNT(br.id) as borrow_count
            FROM books b
            JOIN borrowings br ON b.id = br.book_id
            GROUP BY b.id
            ORDER BY borrow_count DESC
            LIMIT 10
        """)
        popular_books = [{'title': r[0], 'author': r[1], 'borrow_count': r[2]} for r in cursor.fetchall()]
    
    context = {
        'stats': stats,
        'daily_activity': daily_activity,
        'active_users': active_users,
        'popular_books': popular_books
    }
    return render(request, 'admin/system_stats.html', context)

@login_required
@role_required('admin')
def manage_database(request):
    """Admin panel to manage database rows"""
    if request.method == 'POST':
        table_name = request.POST.get('table_name')
        row_id = request.POST.get('row_id')
        
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (row_id,))
                conn.commit()
                return JsonResponse({'success': True, 'message': f'Row {row_id} deleted from {table_name}'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)})
    
    tables = ['users', 'students', 'books', 'borrowings', 'audit_logs']
    table_data = {}
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"SELECT * FROM {table} LIMIT 50")
            rows = cursor.fetchall()
            if rows:
                columns = [col[0] for col in cursor.description]
                table_data[table] = [dict(zip(columns, row)) for row in rows]
            else:
                table_data[table] = []
    
    return render(request, 'admin/manage_database.html', {'table_data': table_data})

# ==================== COMMON VIEWS ====================
def access_denied(request):
    """Access denied page"""
    return render(request, 'access_denied.html', {'message': 'You do not have permission to access this page.'})

# ==================== REPORTS API VIEWS ====================

@login_required
@role_required('admin', 'librarian')
def reports_view(request):
    """Reports page for both admin and librarian"""
    from datetime import date
    context = {
        'today': date.today().isoformat(),
        'user': get_logged_in_user(request)
    }
    return render(request, 'admin/reports.html', context)


@login_required
@role_required('admin', 'librarian')
def reports_api_borrowings(request):
    """API for borrowings report data"""
    from .db_config import Database
    from datetime import datetime
    
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status = request.GET.get('status', 'all')
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT br.id, br.borrowing_code, br.borrow_date, br.due_date, 
                   br.return_date, br.status, br.fine_amount,
                   b.title as book_title, b.book_code,
                   u.full_name as student_name, s.student_id
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            JOIN students s ON br.student_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND br.borrow_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND br.borrow_date <= %s"
            params.append(end_date)
        if status != 'all':
            query += " AND br.status = %s"
            params.append(status)
        
        query += " ORDER BY br.borrow_date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Get column names
        columns = [col[0] for col in cursor.description]
        borrowings = []
        for row in rows:
            item = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (datetime, date)):
                    value = str(value)
                item[col] = value if value is not None else None
            borrowings.append(item)
        
        # Calculate stats
        cursor.execute("SELECT COUNT(*) FROM borrowings")
        total_borrowings = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM borrowings WHERE status = 'returned'")
        total_returns = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM borrowings WHERE status = 'overdue' OR (status='borrowed' AND due_date < CURDATE())")
        total_overdue = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) FROM borrowings")
        total_fines = float(cursor.fetchone()[0] or 0)
    
    return JsonResponse({
        'borrowings': borrowings,
        'total_borrowings': total_borrowings,
        'total_returns': total_returns,
        'total_overdue': total_overdue,
        'total_fines': total_fines
    })


@login_required
@role_required('admin', 'librarian')
def reports_api_students(request):
    """API for students report data"""
    from .db_config import Database
    
    department = request.GET.get('department', 'all')
    status = request.GET.get('status', 'all')
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT u.id, u.full_name, u.email, u.phone, u.is_active, u.created_at,
                   s.student_id, s.department, s.semester, s.total_books_borrowed,
                   s.current_books_borrowed, s.fine_amount
            FROM users u
            JOIN students s ON u.id = s.user_id
            WHERE u.role = 'student'
        """
        params = []
        
        if department != 'all':
            query += " AND s.department = %s"
            params.append(department)
        if status != 'all':
            is_active = status == 'active'
            query += " AND u.is_active = %s"
            params.append(is_active)
        
        query += " ORDER BY u.full_name"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        students = []
        for row in rows:
            student = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (datetime, date)):
                    value = str(value)
                student[col] = value if value is not None else None
            students.append(student)
        
        # Calculate stats
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
        total_students = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND is_active = 1")
        active_students = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM students WHERE total_books_borrowed > 0")
        students_with_borrowings = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COALESCE(SUM(total_books_borrowed), 0) FROM students")
        total_borrowings = cursor.fetchone()[0] or 0
    
    return JsonResponse({
        'students': students,
        'total_students': total_students,
        'active_students': active_students,
        'students_with_borrowings': students_with_borrowings,
        'total_borrowings': total_borrowings
    })


@login_required
@role_required('admin', 'librarian')
def reports_api_books(request):
    """API for books report data"""
    from .db_config import Database
    
    category = request.GET.get('category', 'all')
    availability = request.GET.get('availability', 'all')
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM books WHERE 1=1"
        params = []
        
        if category != 'all':
            query += " AND category = %s"
            params.append(category)
        if availability == 'available':
            query += " AND available_copies > 0"
        elif availability == 'borrowed':
            query += " AND available_copies = 0"
        
        query += " ORDER BY title"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        books = []
        for row in rows:
            book = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (datetime, date)):
                    value = str(value)
                book[col] = value if value is not None else None
            books.append(book)
        
        # Calculate stats
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(available_copies) FROM books")
        available_sum = cursor.fetchone()[0]
        available_books = available_sum if available_sum else 0
        
        cursor.execute("SELECT COUNT(DISTINCT category) FROM books WHERE category IS NOT NULL AND category != ''")
        total_categories = cursor.fetchone()[0] or 0
        
        borrowed_books = total_books - available_books
    
    return JsonResponse({
        'books': books,
        'total_books': total_books,
        'available_books': available_books,
        'borrowed_books': borrowed_books,
        'total_categories': total_categories
    })


@login_required
@role_required('admin', 'librarian')
def reports_api_fines(request):
    """API for fines report data"""
    from .db_config import Database
    
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT br.id, br.fine_amount, br.fine_paid, br.due_date, br.return_date,
                   DATEDIFF(br.return_date, br.due_date) as days_overdue,
                   b.title as book_title,
                   u.full_name as student_name, s.student_id
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            JOIN students s ON br.student_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE br.fine_amount > 0
        """
        params = []
        
        if start_date:
            query += " AND br.return_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND br.return_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY br.return_date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        fines = []
        for row in rows:
            fine = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (datetime, date)):
                    value = str(value)
                fine[col] = value if value is not None else None
            fines.append(fine)
        
        # Calculate stats
        cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) FROM borrowings")
        total_fines = float(cursor.fetchone()[0] or 0)
        
        cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) FROM borrowings WHERE fine_paid = 1")
        paid_fines = float(cursor.fetchone()[0] or 0)
        
        unpaid_fines = total_fines - paid_fines
        
        cursor.execute("SELECT COUNT(*) FROM borrowings WHERE fine_amount > 0")
        fine_count = cursor.fetchone()[0] or 0
    
    return JsonResponse({
        'fines': fines,
        'total_fines': total_fines,
        'paid_fines': paid_fines,
        'unpaid_fines': unpaid_fines,
        'fine_count': fine_count
    })


@login_required
@role_required('admin', 'librarian')
def reports_api_popular(request):
    """API for popular books report"""
    from .db_config import Database
    
    period = request.GET.get('period', 'month')
    limit = int(request.GET.get('limit', 10))
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        date_condition = ""
        if period == 'month':
            date_condition = "AND MONTH(br.borrow_date) = MONTH(CURDATE()) AND YEAR(br.borrow_date) = YEAR(CURDATE())"
        elif period == 'quarter':
            date_condition = "AND br.borrow_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)"
        elif period == 'year':
            date_condition = "AND YEAR(br.borrow_date) = YEAR(CURDATE())"
        
        query = f"""
            SELECT b.id, b.title, b.author, b.category, COUNT(br.id) as borrow_count
            FROM books b
            JOIN borrowings br ON b.id = br.book_id
            WHERE 1=1 {date_condition}
            GROUP BY b.id
            ORDER BY borrow_count DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        books = []
        for row in rows:
            book = {}
            for i, col in enumerate(columns):
                value = row[i]
                book[col] = value if value is not None else None
            books.append(book)
    
    return JsonResponse({'books': books})


@login_required
@role_required('admin', 'librarian')
def reports_api_activity(request):
    """API for activity report"""
    from .db_config import Database
    from datetime import datetime, timedelta
    
    period = request.GET.get('period', 'daily')
    
    with Database.get_connection() as conn:
        cursor = conn.cursor()
        
        # Build date filter based on period
        date_filter = ""
        if period == 'daily':
            date_filter = "DATE(created_at) = CURDATE()"
        elif period == 'weekly':
            date_filter = "created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        else:  # monthly
            date_filter = "created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        
        # Get activities
        cursor.execute(f"""
            SELECT al.*, u.username, u.role
            FROM audit_logs al
            JOIN users u ON al.user_id = u.id
            WHERE {date_filter}
            ORDER BY al.created_at DESC
            LIMIT 100
        """)
        
        columns = [col[0] for col in cursor.description]
        activities = []
        for row in cursor.fetchall():
            activity = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (datetime, date)):
                    value = str(value)
                activity[col] = value if value is not None else None
            activities.append(activity)
        
        # Calculate stats
        cursor.execute(f"SELECT COUNT(*) FROM audit_logs WHERE {date_filter}")
        total_actions = cursor.fetchone()[0] or 0
        
        cursor.execute(f"SELECT COUNT(*) FROM audit_logs WHERE action = 'LOGIN' AND {date_filter}")
        total_logins = cursor.fetchone()[0] or 0
        
        cursor.execute(f"SELECT COUNT(DISTINCT user_id) FROM audit_logs WHERE {date_filter}")
        active_users = cursor.fetchone()[0] or 0
    
    return JsonResponse({
        'activities': activities,
        'total_actions': total_actions,
        'total_logins': total_logins,
        'active_users': active_users
    })