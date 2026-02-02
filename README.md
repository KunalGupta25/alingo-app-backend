# Alingo - Backend (Django REST API)

A robust Django REST Framework backend API for the Alingo mobile application, featuring phone authentication, user management, and identity verification workflows.

## 🚀 Features

- **Phone Number Authentication** - OTP-based authentication system
- **MongoDB Integration** - NoSQL database for flexible data storage
- **User Management** - Complete user profile and verification system
- **Identity Verification** - Admin panel for manual verification approval
- **Firebase Storage** - Secure document and image storage
- **RESTful API** - Clean, well-structured API endpoints
- **CORS Support** - Configured for cross-origin requests

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- **Python** (3.11 or higher)
- **MongoDB** (running locally or remote instance)
- **pip** - Python package manager

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/KunalGupta25/alingo-app-backend.git
   cd alingo-app-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   
   Copy `.env.example` to `.env` and update the values:
   ```bash
   cp .env.example .env
   ```
   
   Update the following in `.env`:
   ```env
   # MongoDB Configuration
   MONGO_URI=mongodb://localhost:27017/
   MONGO_DB_NAME=alingo
   
   # Django Settings
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # Firebase Admin SDK
   FIREBASE_CREDENTIALS_PATH=path/to/serviceAccountKey.json
   
   # CORS Settings
   CORS_ALLOWED_ORIGINS=http://localhost:8081,exp://192.168.x.x:8081
   ```

5. **Setup Firebase Admin SDK**
   
   - Download your Firebase Admin SDK service account key from Firebase Console
   - Place it in the backend directory
   - Update `FIREBASE_CREDENTIALS_PATH` in `.env`

6. **Run Django migrations** (for session management)
   ```bash
   python manage.py migrate
   ```

## 🚦 Running the Application

### Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

The API will be available at `http://localhost:8000`

### Access Admin Panel

Visit `http://localhost:8000/admin/verification/` to access the verification admin panel.

## 📁 Project Structure

```
backend/
├── apps/                          # Django applications
│   ├── authentication/            # Authentication app
│   │   ├── views.py              # Login, register, OTP views
│   │   ├── services.py           # User & OTP business logic
│   │   ├── otp_service.py        # OTP generation/verification
│   │   └── urls.py               # Auth routes
│   ├── verification/              # Identity verification app
│   │   ├── admin.py              # Admin panel for verification
│   │   ├── views.py              # Verification endpoints
│   │   ├── services.py           # Verification business logic
│   │   ├── auth.py               # Token authentication
│   │   ├── auth_middleware.py    # Auth middleware
│   │   └── urls.py               # Verification routes
│   └── core/                      # Core utilities
│       ├── firebase_utils.py     # Firebase Storage helper
│       └── views.py              # Health check endpoint
├── config/                        # Django configuration
│   ├── settings.py               # Main settings
│   ├── urls.py                   # Root URL configuration
│   └── wsgi.py                   # WSGI configuration
├── database/                      # Database utilities
│   └── mongo.py                  # MongoDB connection helper
├── templates/                     # HTML templates
│   └── admin/                    # Admin panel templates
│       ├── login.html            # Admin login page
│       └── verification_list.html # Verification list view
├── media/                         # Uploaded files (gitignored)
├── manage.py                      # Django management script
├── requirements.txt               # Python dependencies
├── .env.example                  # Environment variables template
└── .gitignore                    # Git ignore rules
```

## 🔐 API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/authentication/register/` | Register new user |
| POST | `/api/authentication/verify-otp/` | Verify OTP code |
| POST | `/api/authentication/login/` | User login |

### Verification

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/verification/status/` | Get user verification status | ✅ |
| POST | `/api/verification/submit/` | Submit identity documents | ✅ |

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/core/health/` | Health check |

## 📊 Database Schema (MongoDB)

### Users Collection
```json
{
  "_id": "ObjectId",
  "phone": "+1234567890",
  "full_name": "John Doe",
  "age": 25,
  "bio": "User bio",
  "gender": "Male",
  "verification_status": "PENDING|VERIFIED|REJECTED",
  "created_at": "ISO Date",
  "updated_at": "ISO Date"
}
```

### Verifications Collection
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "document_url": "firebase_storage_url",
  "face_url": "firebase_storage_url",
  "status": "PENDING|APPROVED|REJECTED",
  "created_at": "ISO Date",
  "updated_at": "ISO Date",
  "reviewed_at": "ISO Date",
  "admin_notes": "string"
}
```

### OTPs Collection
```json
{
  "_id": "ObjectId",
  "phone": "+1234567890",
  "otp": "123456",
  "created_at": "ISO Date",
  "expires_at": "ISO Date",
  "verified": false
}
```

## 🔑 Key Technologies

- **Django 6.0.1** - Web framework
- **Django REST Framework 3.16.1** - RESTful API toolkit
- **PyMongo 4.16.0** - MongoDB driver
- **Firebase Admin SDK 7.1.0** - Firebase integration
- **django-cors-headers 4.9.0** - CORS middleware
- **python-dotenv 1.2.1** - Environment variable management

## 📦 Main Dependencies

```txt
Django==6.0.1
djangorestframework==3.16.1
pymongo==4.16.0
firebase_admin==7.1.0
django-cors-headers==4.9.0
python-dotenv==1.2.1
```

## 🔧 Configuration

### MongoDB Collections

The application uses three main collections:
- `users` - User profiles and authentication data
- `verifications` - Identity verification submissions
- `otps` - One-time password codes

### Firebase Storage

Identity documents are stored in Firebase Storage with the following structure:
```
verifications/
  └── {user_id}/
      ├── document_{timestamp}.jpg
      └── face_{timestamp}.jpg
```

### CORS Configuration

Update `CORS_ALLOWED_ORIGINS` in `settings.py` or `.env` to allow requests from your frontend:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8081",
    "exp://192.168.1.100:8081",  # Replace with your local IP
]
```

## 🛡️ Authentication

The API uses a simple token-based authentication:
1. User logs in and receives a token
2. Token is stored in the `users` collection
3. Protected endpoints require `Authorization: Bearer {token}` header

## 🐛 Troubleshooting

### MongoDB Connection Issues
```bash
# Check if MongoDB is running
mongosh

# If not installed, visit: https://www.mongodb.com/try/download/community
```

### Firebase Permission Errors
- Verify your service account key is valid
- Check Firebase Storage rules allow uploads
- Ensure the file path in `.env` is correct

### CORS Errors
- Add your frontend URL to `CORS_ALLOWED_ORIGINS`
- Clear browser cache if changes don't reflect

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

## 📝 Development Notes

### OTP System
- OTPs expire after 10 minutes
- For development, OTPs are logged to console
- In production, integrate with an SMS service provider (Twilio, etc.)

### Admin Panel
- Currently accessible without authentication
- Add authentication for production deployment
- Admin can approve/reject verification requests with notes

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Configure proper `SECRET_KEY`
- [ ] Set up production MongoDB instance
- [ ] Configure production `ALLOWED_HOSTS`
- [ ] Set up proper SMS provider for OTP delivery
- [ ] Add admin authentication
- [ ] Configure static files serving
- [ ] Set up proper logging
- [ ] Enable HTTPS

### Recommended Hosting

- **Backend**: Railway, Render, Heroku, AWS EC2
- **Database**: MongoDB Atlas
- **Storage**: Firebase Storage (already configured)

## 📄 License

This project is private and proprietary.

## 👥 Author

**Kunal Gupta**
- GitHub: [@KunalGupta25](https://github.com/KunalGupta25)

## 🤝 Contributing

This is a private repository. Please contact the owner for collaboration opportunities.

---

For frontend repository, visit: [alingo-app-front](https://github.com/KunalGupta25/alingo-app-front)
