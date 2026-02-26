#!/bin/bash

# Kirinyaga Hostels Deployment Script
# For Oracle Cloud, Supabase, and Cloudflare Pages

set -e

echo "🚀 Starting Kirinyaga Hostels Platform Deployment"
echo "================================================"

# Load environment variables
if [ -f ../backend/.env ]; then
    export $(grep -v '^#' ../backend/.env | xargs)
else
    echo "❌ .env file not found. Please create one from .env.template"
    exit 1
fi

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
    else
        echo "❌ $1 failed"
        exit 1
    fi
}

echo ""
echo "📦 Step 1: Installing Dependencies"
echo "----------------------------------"
cd ../backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
check_status "Python dependencies installed"

echo ""
echo "🗄️  Step 2: Database Migration (Supabase)"
echo "----------------------------------------"
python manage.py migrate
check_status "Database migrations"

echo ""
echo "👤 Step 3: Creating Superuser"
echo "-----------------------------"
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('$ADMIN_EMAIL', 'Admin123!', phone_number='$SUPER_ADMIN_PHONE')
    print('✅ Superuser created')
else:
    print('✅ Superuser already exists')
"

echo ""
echo "📁 Step 4: Collecting Static Files"
echo "----------------------------------"
python manage.py collectstatic --noinput
check_status "Static files collected"

echo ""
echo "🐳 Step 5: Building Docker Containers"
echo "-------------------------------------"
cd ../deployment
docker-compose build
check_status "Docker build"

echo ""
echo "🚢 Step 6: Starting Services"
echo "----------------------------"
docker-compose up -d
check_status "Services started"

echo ""
echo "🔍 Step 7: Checking Service Health"
echo "----------------------------------"
sleep 10
curl -f http://localhost:8000/api/health/ || echo "⚠️  Health check failed, but continuing..."

echo ""
echo "🔒 Step 8: Setting up SSL (if domain configured)"
echo "------------------------------------------------"
if [ ! -z "$DOMAIN_NAME" ]; then
    docker-compose exec nginx certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email $ADMIN_EMAIL
    check_status "SSL certificates"
fi

echo ""
echo "📊 Step 9: Container Status"
echo "---------------------------"
docker-compose ps

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Access your services at:"
echo "   API: https://api.kirinyagahostels.com"
echo "   Student Portal: https://student.kirinyagahostels.com"
echo "   Owner Portal: https://owner.kirinyagahostels.com"
echo "   Admin Portal: https://admin.kirinyagahostels.com"
echo ""
echo "📝 Admin Credentials:"
echo "   Email: $ADMIN_EMAIL"
echo "   Password: Admin123! (change immediately)"
echo ""
echo "🔧 Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Restart: docker-compose restart"
echo "   Stop: docker-compose down"
echo "================================================"