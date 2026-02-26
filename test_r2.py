# test_r2.py
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Setup Django
django.setup()

# Now import Django-specific modules
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

def test_r2():
    print("=" * 50)
    print("Testing Cloudflare R2 connection...")
    print("=" * 50)
    
    # Print current settings (without sensitive data)
    print(f"Using endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print(f"Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"Region: {settings.AWS_S3_REGION_NAME}")
    print("-" * 50)
    
    try:
        # Upload test file
        test_content = b"Hello, Cloudflare R2! This is a test file."
        filename = default_storage.save(
            'test/test-file.txt', 
            ContentFile(test_content)
        )
        print(f"✅ Uploaded: {filename}")
        
        # Get URL
        url = default_storage.url(filename)
        print(f"✅ URL: {url}")
        
        # Check exists
        exists = default_storage.exists(filename)
        print(f"✅ File exists: {exists}")
        
        # Read back content
        with default_storage.open(filename, 'r') as f:
            content = f.read()
            print(f"✅ Content: {content}")
        
        # Clean up
        default_storage.delete(filename)
        print(f"✅ Deleted test file")
        
        print("=" * 50)
        print("🎉 R2 configuration is working perfectly!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check your .env file has correct credentials")
        print("2. Verify your R2 bucket exists")
        print("3. Ensure your API token has read/write permissions")
        return False
    
    return True

if __name__ == "__main__":
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("Creating .env file from template...")
        # Create a basic .env template
        with open('.env', 'w') as f:
            f.write("""# Cloudflare R2 Configuration
AWS_ACCESS_KEY_ID=your-access-key-here
AWS_SECRET_ACCESS_KEY=your-secret-key-here
AWS_STORAGE_BUCKET_NAME=kirinyaga-hostels
AWS_S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
AWS_S3_USE_SSL=True
""")
        print("✅ Created .env file. Please edit it with your actual R2 credentials!")
        sys.exit(1)
    
    test_r2()