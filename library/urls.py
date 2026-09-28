# library/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Student URLs
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/books/', views.student_books, name='student_books'),
    path('student/borrow/', views.student_borrow, name='student_borrow'),
    path('student/return/', views.student_return, name='student_return'),
    path('student/history/', views.student_history, name='student_history'),
    path('student/profile/', views.student_profile, name='student_profile'),
    
    # Librarian URLs
    path('librarian/dashboard/', views.librarian_dashboard, name='librarian_dashboard'),
    path('librarian/books/', views.manage_books, name='manage_books'),
    path('librarian/books/add/', views.add_book, name='add_book'),
    path('librarian/books/edit/<int:book_id>/', views.edit_book, name='edit_book'),
    path('librarian/books/delete/<int:book_id>/', views.delete_book, name='delete_book'),
    path('librarian/books/json/<int:book_id>/', views.get_book_json, name='get_book_json'),
    path('librarian/students/', views.manage_students, name='manage_students'),
    path('librarian/students/<int:user_id>/json/', views.get_student_json, name='get_student_json'),
    path('librarian/students/<str:student_id>/history/json/', views.get_student_history_json, name='get_student_history_json'),
    path('librarian/students/toggle/', views.toggle_student_status, name='toggle_student_status'),
    path('librarian/students/update/', views.update_student, name='update_student'),
    path('librarian/students/<str:student_id>/', views.student_detail, name='student_detail'),
    path('librarian/borrow/', views.process_borrow, name='process_borrow'),
    path('librarian/return/', views.process_return, name='process_return'),
    path('librarian/borrowings/', views.all_borrowings, name='all_borrowings'),
    path('librarian/search/', views.search_books_librarian, name='search_books_librarian'),
    path('librarian/reports/', views.librarian_reports, name='librarian_reports'),
    
    # Admin URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.manage_users, name='manage_users'),
    path('admin/logs/', views.system_logs, name='system_logs'),
    path('admin/backup/', views.backup_database, name='backup_database'),
    path('admin/settings/', views.system_settings, name='system_settings'),
    path('admin/stats/', views.system_stats, name='system_stats'),
    path('admin/database/', views.manage_database, name='manage_database'),
    
    # Error pages
    path('access-denied/', views.access_denied, name='access_denied'),
    # Add to your library/urls.py

# Reports
path('reports/', views.reports_view, name='reports'),
path('reports/api/borrowings/', views.reports_api_borrowings, name='reports_api_borrowings'),
path('reports/api/students/', views.reports_api_students, name='reports_api_students'),
path('reports/api/books/', views.reports_api_books, name='reports_api_books'),
path('reports/api/fines/', views.reports_api_fines, name='reports_api_fines'),
path('reports/api/popular/', views.reports_api_popular, name='reports_api_popular'),
path('reports/api/activity/', views.reports_api_activity, name='reports_api_activity'),
path('student/profile/', views.student_profile, name='student_profile'),
path('change-password/', views.change_password, name='change_password'),
]