# TextMorph – Secure LLM-Based NLP Platform (Milestone 4)
# Overview

TextMorph is a secure, scalable, and interactive NLP web application built using Streamlit.
Milestone 4 enhances the previous version by integrating Admin Dashboard, advanced analytics, user personalization, and improved UI/UX into a complete end-to-end system.

# Milestone 4 Objectives
Integrate all Milestone 3 features
Build Admin Dashboard (Management + Analytics)
Implement User Profile Personalization
Add Data Visualization & Feedback Analysis
Ensure full deployment readiness

# Key Features
# Authentication & Security
User Registration & Login
Email-based OTP verification
Password hashing using bcrypt
JWT-based session management
Regex-based password validation
Secure session handling

# Admin Dashboard (Management & Analytics)
# User Management
Promote users to Admin role
Lock / Unlock user accounts
Delete users
View registered users

# Activity Tracking
Real-time active users monitoring
Track system usage history
Log user activities

# Data Visualization
Interactive charts showing:
Models being used
Languages used
Most used features

# Feedback Analysis
Analyze user feedback
Generate WordCloud visualization

# Data Export
Export:
User details
Usage logs
Feedback data

# User Dashboard & Profile Personalization
# Security Controls
Update email address
Change password



# UI/UX Enhancements
Modern Neon-themed UI
Improved layout and navigation
Interactive components

# NLP Functionalities
Text Summarization (Transformer models)
Tokenization using NLTK
Dataset-based NLP processing
Multi-dataset support

# Text Analysis
Readability analysis using textstat
Word, sentence, and syllable metrics
Visualization using charts

# Data & Logging
SQLite database integration
Feature usage tracking
System event logging
Active user tracking

# Deployment
Streamlit web application
Public access using ngrok
Google Drive support (optional)

# Tech Stack
Frontend/UI: Streamlit
Backend: Python
Security: JWT, bcrypt, OTP
NLP Libraries:
Transformers (Hugging Face)
NLTK
Datasets
Database: SQLite
Visualization: Plotly, WordCloud
Deployment: ngrok

# Installation & Setup
1. Clone Repository
git clone <your-repo-link>
cd TextMorph
2. Install Dependencies
pip install -r requirements.txt

Or manually:

pip install streamlit pyjwt bcrypt python-dotenv pyngrok nltk \
transformers torch sentencepiece accelerate pandas datasets \
textstat plotly wordcloud PyPDF2

# Run the Application
streamlit run app.py

# Run with ngrok (Public URL)
from pyngrok import ngrok
public_url = ngrok.connect(8501)
print(public_url)

# Environment Variables
Set the following:
EMAIL_USER → Your email
EMAIL_PASSWORD → App password
NGROK_AUTHTOKEN → ngrok token
HF_TOKEN → Hugging Face token (optional)

# Datasets Used
CNN/DailyMail → Summarization
XSum → Abstractive summarization
PAWS → Paraphrase tasks

# Security Features
Password hashing using bcrypt
JWT-based authentication
OTP verification system
Input validation using regex
Session timeout handling

# Future Scope
Docker containerization
Cloud deployment (AWS / GCP / Azure)
Role-based access control (advanced)
Real-time analytics dashboard
Integration with advanced LLM APIs

# Conclusion

The TextMorph (Milestone 4) project successfully delivers a complete, secure, and scalable NLP-based web application by integrating all features from previous milestones with advanced enhancements. The system now includes a fully functional Admin Dashboard, user profile personalization, and interactive analytics, making it a comprehensive end-to-end solution.

Through this milestone, key objectives such as secure authentication, real-time activity tracking, data visualization, and feedback analysis have been effectively implemented. The addition of modern UI/UX design and deployment support further improves usability and accessibility.

Overall, this project demonstrates the practical application of Natural Language Processing, secure system design, and full-stack development, preparing it for real-world deployment and future scalability.
