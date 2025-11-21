#!/bin/bash
set -e

echo "🚀 Suremind FastAPI - Quick Setup"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "✅ .env file already exists"
else
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env

    # Generate a secure JWT secret
    JWT_SECRET=$(openssl rand -hex 32)

    # Update .env with generated secret
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    else
        # Linux
        sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    fi

    echo "✅ Created .env file with secure JWT_SECRET"
    echo ""
    echo "⚠️  Please review .env and update:"
    echo "   - POSTGRES_PASSWORD (use a strong password)"
    echo "   - CORS_ORIGINS (your Next.js URL)"
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🔨 Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are healthy
if docker-compose ps | grep -q "healthy"; then
    echo "✅ All services are running!"
else
    echo "⚠️  Services are starting... Run 'docker-compose ps' to check status"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 API:  http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
echo ""
echo "Useful commands:"
echo "  make logs       - View all logs"
echo "  make test       - Run tests"
echo "  make shell      - Backend shell"
echo "  make help       - See all commands"
echo ""
echo "Next steps:"
echo "  1. Review and update .env file"
echo "  2. Visit http://localhost:8000/docs"
echo "  3. Register a user via POST /api/v1/auth/register"
echo ""
