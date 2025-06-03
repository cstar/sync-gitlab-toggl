#!/usr/bin/env python3
"""
Build script for Lambda deployment package
Copies only necessary files to src/ directory to avoid CDK path issues
"""

import os
import shutil
import glob
from pathlib import Path

def clean_src_directory():
    """Remove and recreate src directory"""
    src_dir = Path("src")
    if src_dir.exists():
        shutil.rmtree(src_dir)
    src_dir.mkdir()
    print("✅ Cleaned src/ directory")

def copy_python_files():
    """Copy necessary Python files"""
    files_to_copy = [
        "lambda_handler.py",
        "config.py", 
        "config_lambda.py",
        "sync_service.py",
        "toggl_client.py", 
        "gitlab_client.py",
        "requirements.txt"
    ]
    
    copied_count = 0
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy2(file_name, "src/")
            copied_count += 1
            print(f"📁 Copied {file_name}")
        else:
            print(f"⚠️  File not found: {file_name}")
    
    print(f"✅ Copied {copied_count} files to src/")

def create_lambda_requirements():
    """Create Lambda-specific requirements.txt with only necessary dependencies"""
    lambda_requirements = [
        "requests>=2.31.0",
        "requests-toolbelt>=1.0.0", 
        "python-gitlab>=4.4.0",
        "pytz>=2023.3",
        "python-dotenv>=1.0.0",
        "boto3>=1.26.0",  # For AWS Secrets Manager
        "click>=8.1.7"  # For CLI (optional in Lambda but needed for imports)
    ]
    
    with open("src/requirements.txt", "w") as f:
        f.write("\n".join(lambda_requirements))
    
    print("✅ Created Lambda-specific requirements.txt")

def main():
    """Main build process"""
    print("🔨 Building Lambda deployment package...")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    clean_src_directory()
    copy_python_files() 
    create_lambda_requirements()
    
    print("\n🎉 Lambda package built successfully in src/ directory")
    print("   Files included:")
    for file_path in sorted(Path("src").glob("*")):
        print(f"   - {file_path.name}")

if __name__ == "__main__":
    main() 