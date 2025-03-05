# Frontend Deployment Guide

This guide provides detailed instructions for deploying the AI Agentic Deals System frontend to various environments including local, development, staging, and production.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [AWS Deployment](#aws-deployment)
   - [S3 Hosting with CloudFront](#s3-hosting-with-cloudfront)
   - [AWS Amplify Deployment](#aws-amplify-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Scripts](#deployment-scripts)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying the frontend, ensure you have:

- Node.js (version 16.x or later)
- npm or yarn package manager
- AWS CLI (for AWS deployments)
- AWS account with appropriate permissions (for AWS deployments)
- Domain name (if using custom domain)
- Access to the project repository

## Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/aideals.git
   cd aideals
   ```

2. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

3. Install dependencies:
   ```bash
   npm install
   # or
   yarn install
   ```

4. Create a `.env.local` file with the required environment variables:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
   ```

5. Start the development server:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

6. Access the application at `http://localhost:3000`

## AWS Deployment

### S3 Hosting with CloudFront

This approach uses Amazon S3 for static website hosting and CloudFront as a CDN.

#### Prerequisites

- AWS CLI installed and configured
- S3 bucket for hosting the static site
- CloudFront distribution (optional, but recommended)
- ACM certificate for HTTPS (if using custom domain)

#### Deployment Steps

1. **Build the Frontend Application**

   Create a production build of the frontend:
   ```bash
   npm run build
   # or
   yarn build
   ```

2. **Create an S3 Bucket (if not existing)**

   ```bash
   aws s3 mb s3://your-bucket-name
   ```

3. **Configure S3 for Static Website Hosting**

   ```bash
   aws s3 website s3://your-bucket-name --index-document index.html --error-document index.html
   ```

4. **Set S3 Bucket Policy for Public Access**

   Create a policy file `bucket-policy.json`:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PublicReadGetObject",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::your-bucket-name/*"
       }
     ]
   }
   ```

   Apply the policy:
   ```bash
   aws s3api put-bucket-policy --bucket your-bucket-name --policy file://bucket-policy.json
   ```

5. **Upload the Build Files to S3**

   ```bash
   aws s3 sync ./out/ s3://your-bucket-name --delete
   ```

6. **Create CloudFront Distribution (recommended)**

   If you want to use CloudFront as a CDN:

   a. Create an SSL certificate in ACM:
   ```bash
   aws acm request-certificate --domain-name yourdomain.com --validation-method DNS --subject-alternative-names www.yourdomain.com
   ```

   b. Create CloudFront distribution:
   ```bash
   aws cloudfront create-distribution \
     --origin-domain-name your-bucket-name.s3.amazonaws.com \
     --default-root-object index.html \
     --aliases yourdomain.com www.yourdomain.com \
     --viewer-certificate "ACMCertificateArn=<certificate-arn>,SSLSupportMethod=sni-only" \
     --default-cache-behavior "TargetOriginId=S3-your-bucket-name,ViewerProtocolPolicy=redirect-to-https,AllowedMethods=GET,HEAD,OPTIONS"
   ```

   c. Configure CloudFront to handle SPA routing:
   ```bash
   aws cloudfront update-distribution --id <distribution-id> \
     --custom-error-responses "Quantity=1,Items=[{ErrorCode=404,ResponseCode=200,ResponsePagePath=/index.html}]"
   ```

7. **Configure DNS (if using custom domain)**

   Update your DNS settings to point to either the S3 website URL or the CloudFront distribution.

   Using Route 53:
   ```bash
   aws route53 change-resource-record-sets --hosted-zone-id <zone-id> \
     --change-batch '{"Changes":[{"Action":"CREATE","ResourceRecordSet":{"Name":"yourdomain.com","Type":"A","AliasTarget":{"HostedZoneId":"Z2FDTNDATAQYW2","DNSName":"<cloudfront-domain>","EvaluateTargetHealth":false}}}]}'
   ```

### AWS Amplify Deployment

AWS Amplify provides a simpler deployment process with built-in CI/CD.

#### Prerequisites

- AWS account with Amplify permissions
- Git repository (GitHub, GitLab, BitBucket, or AWS CodeCommit)

#### Deployment Steps

1. **Install the Amplify CLI**

   ```bash
   npm install -g @aws-amplify/cli
   ```

2. **Configure Amplify**

   ```bash
   amplify configure
   ```

3. **Initialize Amplify in Your Project**

   ```bash
   cd frontend
   amplify init
   ```

4. **Add Hosting to Your Project**

   ```bash
   amplify add hosting
   # Select 'Hosting with Amplify Console'
   ```

5. **Deploy to Amplify**

   ```bash
   amplify publish
   ```

6. **Connect Repository for CI/CD (Alternative)**

   Instead of using the CLI, you can:
   
   a. Go to the AWS Amplify Console
   b. Click "Connect app"
   c. Select your Git provider
   d. Authorize AWS Amplify
   e. Select your repository and branch
   f. Configure build settings
   g. Click "Save and deploy"

## Environment Configuration

### Environment Variables

Create environment-specific `.env` files for different deployment environments:

- `.env.development` - Development environment
- `.env.staging` - Staging environment
- `.env.production` - Production environment

Example `.env.production`:
```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com/ws
```

### Build-time vs. Runtime Configuration

- **Build-time**: Environment variables prefixed with `NEXT_PUBLIC_` are embedded during build
- **Runtime**: For variables that change between environments, consider using runtime config API

## Deployment Scripts

The repository includes PowerShell deployment scripts to automate the process:

### `scripts/deploy_frontend.ps1`

This script automates the frontend deployment process to AWS S3 and CloudFront:

```powershell
# Deploy frontend to S3 and invalidate CloudFront
param(
    [string]$Environment = "production",
    [string]$BucketName = "aideals-frontend-$Environment",
    [string]$CloudFrontDistribution = ""
)

Write-Host "Deploying frontend to $Environment environment..."

# Check prerequisites
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Error "AWS CLI not found. Please install it."
    exit 1
}

# Build the frontend
Write-Host "Building frontend for $Environment..."
Set-Location -Path "$PSScriptRoot/../frontend"

# Use correct env file
Copy-Item -Path ".env.$Environment" -Destination ".env.local" -Force

# Install dependencies
npm install

# Build for production
npm run build

# Export static files
npm run export

# Check if build was successful
if (-not (Test-Path -Path "out")) {
    Write-Error "Build failed. 'out' directory not found."
    exit 1
}

# Upload to S3
Write-Host "Uploading to S3 bucket: $BucketName"
aws s3 sync ./out/ s3://$BucketName --delete

# Invalidate CloudFront cache if distribution ID provided
if ($CloudFrontDistribution) {
    Write-Host "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation --distribution-id $CloudFrontDistribution --paths "/*"
}

Write-Host "Frontend deployment completed successfully!"
```

To use the script:
```powershell
.\scripts\deploy_frontend.ps1 -Environment "production" -BucketName "your-bucket-name" -CloudFrontDistribution "your-distribution-id"
```

## Post-Deployment Verification

After deploying, perform these verification steps:

1. **Check Basic Functionality**
   - Ensure the site loads correctly
   - Verify all static assets load without errors
   - Test navigation between different pages

2. **API Integration**
   - Verify that the frontend can connect to the backend API
   - Check authentication flows
   - Test main application features

3. **Performance Testing**
   - Run Lighthouse tests for performance, accessibility, best practices, and SEO
   - Check page load times in different geographic regions

## Troubleshooting

### Common Issues and Solutions

1. **Static Assets Not Loading**
   - Check CORS configuration on S3 bucket
   - Verify paths in the build files
   - Check CloudFront cache status

2. **API Connection Issues**
   - Verify API URL environment variables
   - Check CORS settings on the backend
   - Test API endpoints directly

3. **Routing Issues with SPA**
   - Ensure CloudFront is configured to redirect 404s to index.html
   - Check routing configuration in Next.js

4. **Caching Issues**
   - Create a CloudFront invalidation
   - Add version parameters to asset URLs
   - Check browser caching settings

### Debugging Techniques

1. **Check Browser Developer Tools**
   - Examine network requests
   - Look for console errors
   - Analyze application performance

2. **CloudFront and S3 Logs**
   - Enable access logging on S3 and CloudFront
   - Analyze request patterns and errors

3. **Environment Variables**
   - Verify that environment variables are correctly set
   - Check that variables are accessible in the application 