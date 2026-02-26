# test_r2_simple.py
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_r2_connection():
    print("=" * 50)
    print("Testing Cloudflare R2 Connection")
    print("=" * 50)
    
    # Get credentials from .env
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    endpoint = os.getenv('AWS_S3_ENDPOINT_URL')
    bucket = os.getenv('AWS_STORAGE_BUCKET_NAME')
    
    if not all([access_key, secret_key, endpoint, bucket]):
        print("❌ Missing credentials in .env file")
        print("\nPlease make sure your .env file has:")
        print("AWS_ACCESS_KEY_ID=your-key")
        print("AWS_SECRET_ACCESS_KEY=your-secret")
        print("AWS_STORAGE_BUCKET_NAME=your-bucket")
        print("AWS_S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com")
        return
    
    print(f"✅ Endpoint: {endpoint}")
    print(f"✅ Bucket: {bucket}")
    print(f"✅ Access Key ID: {access_key[:5]}...{access_key[-5:]}")
    print("-" * 50)
    
    try:
        # Create S3 client for R2
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        
        # Test: List buckets
        print("Testing connection...")
        response = s3.list_buckets()
        print(f"✅ Connected successfully!")
        print(f"   Found buckets: {[b['Name'] for b in response['Buckets']]}")
        
        # Test: Upload a file
        print("\nTesting upload...")
        test_content = b"Hello R2!"
        s3.put_object(
            Bucket=bucket,
            Key='test-file.txt',
            Body=test_content
        )
        print("✅ Upload successful!")
        
        # Test: Delete file
        print("\nTesting delete...")
        s3.delete_object(Bucket=bucket, Key='test-file.txt')
        print("✅ Delete successful!")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED! R2 is working perfectly!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check if your bucket exists in R2 dashboard")
        print("2. Verify your API token has read/write permissions")
        print("3. Make sure the endpoint URL is correct (includes https://)")
        print("4. Check if your bucket name is spelled correctly")

if __name__ == "__main__":
    test_r2_connection()