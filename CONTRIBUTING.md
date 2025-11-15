# 🤝 Contributing to LUMEN

Thank you for your interest in contributing to LUMEN! This document provides guidelines and instructions for contributing to the project.

---

## 📋 Table of Contents

-   [Code of Conduct](#code-of-conduct)
-   [Getting Started](#getting-started)
-   [Development Workflow](#development-workflow)
-   [Coding Standards](#coding-standards)
-   [Testing Guidelines](#testing-guidelines)
-   [Commit Guidelines](#commit-guidelines)
-   [Pull Request Process](#pull-request-process)
-   [Bug Reports](#bug-reports)
-   [Feature Requests](#feature-requests)

---

## 📜 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in your interactions.

### Expected Behavior

-   Use welcoming and inclusive language
-   Be respectful of differing viewpoints
-   Accept constructive criticism gracefully
-   Focus on what is best for the community
-   Show empathy towards other community members

---

## 🚀 Getting Started

### 1. Fork the Repository

```bash
# Click the "Fork" button on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/Lumen.git
cd Lumen
```

### 2. Set Up Development Environment

Follow the [Setup Guide](SETUP.md) to install dependencies and configure your environment.

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

**Branch Naming Convention:**

-   `feature/` - New features
-   `fix/` - Bug fixes
-   `docs/` - Documentation updates
-   `refactor/` - Code refactoring
-   `test/` - Test additions or modifications
-   `chore/` - Maintenance tasks

---

## 💻 Development Workflow

### Frontend Development

```bash
cd frontend
npm run dev
```

**Key Directories:**

-   `src/app/` - Pages and routes
-   `src/components/` - React components
-   `src/lib/` - Utilities and helpers
-   `src/hooks/` - Custom React hooks

### Backend Development

```bash
cd backend
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows
python app.py
```

**Key Directories:**

-   `routes/` - API endpoints
-   `ai/` - AI agents and ML models
-   `models/` - Database models
-   `utils/` - Utility functions

### Running Tests

```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd backend
pytest
```

---

## 📏 Coding Standards

### TypeScript/JavaScript (Frontend)

```typescript
// Use TypeScript for type safety
interface InvoiceData {
	id: number;
	vendor: string;
	amount: number;
}

// Use arrow functions for components
export const InvoiceCard: React.FC<InvoiceData> = ({ id, vendor, amount }) => {
	return <div className="invoice-card">{/* Component content */}</div>;
};

// Use descriptive variable names
const totalSpendingAmount = calculateTotal(invoices);

// Add comments for complex logic
// Calculate spending trend using linear regression
const trend = calculateTrend(historicalData);
```

**Style Guidelines:**

-   Use 2 spaces for indentation
-   Use single quotes for strings
-   Add semicolons
-   Max line length: 100 characters
-   Use Prettier for formatting

### Python (Backend)

```python
"""Module docstring describing purpose"""

from typing import List, Dict, Any


class InvoiceProcessor:
    """Process invoice data and extract information.

    Attributes:
        api_key: API key for external services
        max_retries: Maximum number of retry attempts
    """

    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.max_retries = max_retries

    def process_invoice(self, file_path: str, user_id: str) -> Dict[str, Any]:
        """Process a single invoice file.

        Args:
            file_path: Path to invoice file
            user_id: User identifier

        Returns:
            Dictionary containing extracted invoice data

        Raises:
            ValueError: If file_path is invalid
            ProcessingError: If extraction fails
        """
        # Function implementation
        pass
```

**Style Guidelines:**

-   Follow PEP 8
-   Use 4 spaces for indentation
-   Max line length: 100 characters
-   Use type hints
-   Add docstrings for all functions and classes
-   Use Black for formatting

---

## 🧪 Testing Guidelines

### Frontend Tests

```typescript
// Component test example
import { render, screen } from "@testing-library/react";
import { InvoiceCard } from "./InvoiceCard";

describe("InvoiceCard", () => {
	it("renders invoice data correctly", () => {
		const mockData = {
			id: 1,
			vendor: "TechCorp",
			amount: 1000,
		};

		render(<InvoiceCard {...mockData} />);

		expect(screen.getByText("TechCorp")).toBeInTheDocument();
		expect(screen.getByText("$1,000.00")).toBeInTheDocument();
	});
});
```

### Backend Tests

```python
import pytest
from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    return app.test_client()


def test_extract_endpoint(client):
    """Test invoice extraction endpoint"""
    response = client.post('/extract', data={
        'file': (io.BytesIO(b'test'), 'invoice.pdf'),
        'user_id': 'test_user'
    })

    assert response.status_code == 200
    assert 'invoice_id' in response.json
```

**Testing Requirements:**

-   Write tests for new features
-   Maintain test coverage above 80%
-   Test edge cases and error conditions
-   Use meaningful test names
-   Mock external API calls

---

## 📝 Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

-   `feat` - New feature
-   `fix` - Bug fix
-   `docs` - Documentation changes
-   `style` - Code style changes (formatting)
-   `refactor` - Code refactoring
-   `test` - Test additions or modifications
-   `chore` - Maintenance tasks

**Examples:**

```bash
feat(analytics): add spending forecast component

- Implement time-series forecasting with Prophet
- Add visualization with Recharts
- Include confidence intervals

Closes #123
```

```bash
fix(ocr): handle multi-page PDF extraction

Fixed issue where only first page was processed.
Added proper page iteration logic.

Fixes #456
```

### Commit Best Practices

-   Use present tense ("add feature" not "added feature")
-   Use imperative mood ("move cursor to..." not "moves cursor to...")
-   First line should be 50 characters or less
-   Reference issues and pull requests
-   Separate subject from body with blank line

---

## 🔄 Pull Request Process

### Before Submitting

1. **Update your branch**

    ```bash
    git fetch upstream
    git rebase upstream/main
    ```

2. **Run tests**

    ```bash
    npm test  # Frontend
    pytest    # Backend
    ```

3. **Check code style**

    ```bash
    npm run lint  # Frontend
    black .       # Backend
    ```

4. **Update documentation** if needed

### Submitting Pull Request

1. **Push to your fork**

    ```bash
    git push origin feature/your-feature-name
    ```

2. **Create Pull Request** on GitHub

3. **Fill out PR template**

    - Description of changes
    - Related issue numbers
    - Screenshots (if UI changes)
    - Testing performed

4. **Wait for review**
    - Address reviewer feedback
    - Update PR as needed
    - Keep discussions constructive

### PR Template

```markdown
## Description

Brief description of what this PR does

## Related Issues

Closes #123
Related to #456

## Changes

-   Added X feature
-   Fixed Y bug
-   Refactored Z component

## Screenshots (if applicable)

[Add screenshots here]

## Testing

-   [ ] Unit tests added/updated
-   [ ] Integration tests pass
-   [ ] Manual testing completed

## Checklist

-   [ ] Code follows project style guidelines
-   [ ] Self-review completed
-   [ ] Comments added for complex code
-   [ ] Documentation updated
-   [ ] No new warnings generated
```

---

## 🐛 Bug Reports

### Before Reporting

1. Check existing issues
2. Update to latest version
3. Try to reproduce consistently

### Bug Report Template

```markdown
**Describe the bug**
Clear description of what the bug is

**To Reproduce**
Steps to reproduce:

1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen

**Screenshots**
If applicable, add screenshots

**Environment:**

-   OS: [e.g. Windows 11]
-   Browser: [e.g. Chrome 120]
-   Version: [e.g. 1.0.0]

**Additional context**
Any other relevant information
```

---

## ✨ Feature Requests

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
What you want to happen

**Describe alternatives you've considered**
Alternative solutions or features

**Additional context**
Mockups, examples, or other context

**Would you like to implement this?**
[ ] Yes
[ ] No
[ ] Need guidance
```

---

## 📚 Resources

### Documentation

-   [Setup Guide](SETUP.md)
-   [Architecture](ARCHITECTURE.md)
-   [API Documentation](API_DOCS.md)

### External Resources

-   [Next.js Docs](https://nextjs.org/docs)
-   [Flask Docs](https://flask.palletsprojects.com/)
-   [React Testing Library](https://testing-library.com/react)
-   [pytest Docs](https://docs.pytest.org/)

---

## 🏆 Recognition

Contributors will be recognized in:

-   [README.md](README.md) contributors section
-   Release notes
-   Project documentation

---

## 💬 Getting Help

-   **Discord**: [Join our server](#)
-   **GitHub Discussions**: [Ask questions](https://github.com/CoderUzumaki/Lumen/discussions)
-   **Email**: team@dunder-pressure.dev

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

<div align="center">

**Thank you for contributing to LUMEN! 🎉**

Together, we're building something amazing.

</div>
