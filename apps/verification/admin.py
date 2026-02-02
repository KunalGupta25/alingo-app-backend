"""
Django Admin Configuration for Verification Management
Provides interface for manual review of identity verifications
"""
from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponseRedirect
from database.mongo import get_users_collection
from .services import VerificationService
from .auth import admin_login_required, admin_login, admin_logout
from bson import ObjectId
from datetime import datetime


class VerificationAdmin:
    """Custom admin for MongoDB-based verification system"""
    
    change_list_template = 'admin/verification_list.html'
    
    def get_urls(self):
        """Define custom admin URLs"""
        urls = [
            path('', self.changelist_view, name='verification_changelist'),
            path('login/', admin_login, name='admin_login'),
            path('logout/', admin_logout, name='admin_logout'),
            path('<str:verification_id>/approve/', self.approve_verification, name='approve_verification'),
            path('<str:verification_id>/reject/', self.reject_verification, name='reject_verification'),
        ]
        return urls
    
    @admin_login_required
    def changelist_view(self, request):
        """Display list of pending verifications"""
        # Get all pending verifications
        verifications = VerificationService.get_pending_verifications()
        
        # Enrich with user data
        users_collection = get_users_collection()
        for v in verifications:
            user = users_collection.find_one({'_id': v['user_id']})
            if user:
                v['user_phone'] = user.get('phone', 'Unknown')
                v['user_name'] = user.get('full_name', 'N/A')
            else:
                v['user_phone'] = 'Unknown'
                v['user_name'] = 'N/A'
            
            # Format dates
            if v.get('submitted_at'):
                v['submitted_at_formatted'] = v['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Add image URLs - robust path handling
            import time
            timestamp = int(time.time())
            
            def normalize_media_path(p):
                if not p: return ""
                p = str(p).replace('\\', '/')
                # Remove leading slashes and 'media/' prefixes repeatedly
                while True:
                    old_p = p
                    p = p.lstrip('/')
                    if p.startswith('media/'):
                        p = p[len('media/'):]
                    if p == old_p:
                        break
                return p

            # Use correct field names from database (preferring document_path if it exists)
            doc_path_raw = v.get('document_path') or v.get('document_image_url')
            if doc_path_raw:
                doc_path = normalize_media_path(doc_path_raw)
                v['document_image_url'] = f"/media/{doc_path}?t={timestamp}"

            face_path_raw = v.get('face_path') or v.get('face_image_url')
            if face_path_raw:
                face_path = normalize_media_path(face_path_raw)
                v['face_image_url'] = f"/media/{face_path}?t={timestamp}"
            
            # Make ID string for template
            v['id_str'] = str(v['_id'])
        
        context = {
            'verifications': verifications,
            'title': 'Identity Verifications - Pending Review',
            'has_verifications': len(verifications) > 0,
        }
        
        return render(request, 'admin/verification_list.html', context)
    
    @admin_login_required
    def approve_verification(self, request, verification_id):
        """Approve a verification request"""
        try:
            # Get verification
            verification = VerificationService.get_collection().find_one(
                {'_id': ObjectId(verification_id)}
            )
            
            if verification:
                # Update verification status
                VerificationService.approve_verification(
                    verification_id,
                    admin_user_id=request.user.id if hasattr(request, 'user') else 'admin'
                )
                
                # Update user verification_status to VERIFIED
                users = get_users_collection()
                users.update_one(
                    {'_id': verification['user_id']},
                    {'$set': {'verification_status': 'VERIFIED'}}
                )
                
                # Success message
                from django.contrib import messages
                messages.success(request, f'Verification approved successfully!')
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error approving verification: {str(e)}')
        
        return HttpResponseRedirect('/verification-panel/')
    
    @admin_login_required
    def reject_verification(self, request, verification_id):
        """Reject a verification request"""
        try:
            # Get rejection reason from POST or use default
            reason = request.POST.get('reason', 'Document not clear or invalid')
            
            # Get verification
            verification = VerificationService.get_collection().find_one(
                {'_id': ObjectId(verification_id)}
            )
            
            if verification:
                # Update verification status
                VerificationService.reject_verification(
                    verification_id,
                    admin_user_id=request.user.id if hasattr(request, 'user') else 'admin',
                    reason=reason
                )
                
                # Update user verification_status to REJECTED
                users = get_users_collection()
                users.update_one(
                    {'_id': verification['user_id']},
                    {'$set': {'verification_status': 'REJECTED'}}
                )
                
                # Success message
                from django.contrib import messages
                messages.success(request, f'Verification rejected.')
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error rejecting verification: {str(e)}')
        
        return HttpResponseRedirect('/verification-panel/')


# Create instance
verification_admin = VerificationAdmin()
