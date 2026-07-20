# GurungStore

> GurungStore is an online food & grocery delivery service application built with Django and integrated with the eSewa payment gateway.

## Test Credentials (eSewa Sandbox)

- **Wallet Phone**: `9806800001` or `9806800005`
- **MPIN/Password**: `Nepal@123`

## Getting Started

To get a local copy up and running, follow these steps:

1. Clone the repository:
   ```sh
    git clone https://github.com/umangagurung908/GurungStore-Django-Esewa.git
   ```
2. Create and activate a python virtual environment:

   ```sh
    python -m venv .venv
    .\.venv\Scripts\activate
   ```

3. Install requirements:
   ```sh
    pip install -r requirements.txt
   ```
4. Run database migrations:

   ```sh
    python manage.py makemigrations
    python manage.py migrate
   ```

5. Start the development server:

   ```sh
    python manage.py runserver
   ```

6. Open your browser and navigate to `http://127.0.0.1:8000/`.

---

## E-Commerce Features

### eSewa Payment Integration

This project integrates the standard `django-esewa` package. Signature generation, Base64 callbacks, and server-to-server transaction completeness verification are fully implemented.
