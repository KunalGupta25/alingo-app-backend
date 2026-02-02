"""
Simple Authentication for Verification Panel
"""
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from functools import wraps

# Simple admin credentials (in production, use environment variables)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'alingo@2026'  # Change this in production!


def admin_login_required(view_func):
    """Decorator to require admin login for class methods"""
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        # Check if admin is authenticated
        if not request.session.get('admin_authenticated'):
            return redirect('/verification-panel/login/')
        return view_func(self, request, *args, **kwargs)
    return wrapper


@csrf_exempt
def admin_login(request):
    """Simple login view"""
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            request.session['admin_authenticated'] = True
            return redirect('/verification-panel/')
        else:
            error = 'Invalid username or password'
    
    return render(request, 'admin/login.html', {'error': error})


def admin_logout(request):
    """Logout view"""
    request.session.flush()
    return redirect('/verification-panel/login/')
