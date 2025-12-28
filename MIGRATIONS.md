# 🗄️ Database Migrations Guide

## Setup Alembic

Alembic sudah dikonfigurasi dan siap digunakan!

### Files Created:

-   ✅ `alembic.ini` - Alembic configuration
-   ✅ `alembic/env.py` - Migration environment setup
-   ✅ All models imported and registered

---

## 📋 Migration Commands

### 1. Create Initial Migration

```bash
# Generate migration from current models
alembic revision --autogenerate -m "Initial migration"
```

This will create a migration file in `alembic/versions/` with all 18 models:

-   users
-   comics
-   comic_panels
-   comic_panel_ideas
-   comic_user (likes pivot)
-   comic_views (read history pivot)
-   comments
-   styles
-   genres
-   characters
-   backgrounds
-   asset_music
-   subscription_packages
-   subscriptions
-   payment_transactions
-   transactions
-   notifications
-   banners
-   banner_comic (pivot)

### 2. Apply Migrations

```bash
# Run migrations (create all tables)
alembic upgrade head
```

### 3. Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all
alembic downgrade base
```

### 4. Check Current Version

```bash
# Show current migration version
alembic current

# Show migration history
alembic history
```

### 5. Create New Migration (After Model Changes)

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new field to users"

# Apply the new migration
alembic upgrade head
```

---

## 🔧 Configuration

### Database URL

Database URL is automatically loaded from `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/mamastoria_db
```

### Alembic Settings

-   Migration files: `alembic/versions/`
-   File naming: `YYYY_MM_DD_HHMM-{revision}_{slug}.py`
-   Auto-import all models from `app.models`

---

## ⚠️ Important Notes

### Before Running Migrations:

1. **Setup Database**

    ```bash
    # Create PostgreSQL database
    createdb mamastoria_db
    ```

2. **Configure .env**

    ```env
    DATABASE_URL=postgresql://user:password@localhost:5432/mamastoria_db
    ```

3. **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

### After Migrations:

4. **Seed Master Data** (Optional)
   You may want to seed initial data for:

    - Styles
    - Genres
    - Characters
    - Backgrounds
    - Subscription Packages

    Create a seed script or insert manually.

---

## 📊 Database Schema Overview

### Core Tables:

-   **users** - User accounts & profiles
-   **comics** - Comic data & metadata
-   **comic_panels** - Individual pages/panels
-   **comic_panel_ideas** - Draft panel ideas

### Social Tables:

-   **comments** - Comic reviews
-   **comic_user** - Likes (many-to-many)
-   **comic_views** - Read history (many-to-many)

### Master Data:

-   **styles** - Visual styles
-   **genres** - Comic genres
-   **characters** - Character templates
-   **backgrounds** - Background templates
-   **asset_music** - Music assets

### Monetization:

-   **subscription_packages** - Subscription plans
-   **subscriptions** - User subscriptions
-   **payment_transactions** - DOKU payments
-   **transactions** - General transactions

### System:

-   **notifications** - User notifications
-   **banners** - App banners
-   **banner_comic** - Banner-Comic pivot

---

## 🧪 Testing Migrations

### Test Migration Up/Down:

```bash
# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# Re-apply
alembic upgrade head
```

### Verify Tables Created:

```bash
# Connect to PostgreSQL
psql -d mamastoria_db

# List tables
\dt

# Describe table
\d users
```

---

## 🔄 Common Migration Tasks

### Add New Column:

1. Update model in `app/models/`
2. Generate migration: `alembic revision --autogenerate -m "Add column"`
3. Apply: `alembic upgrade head`

### Modify Column:

1. Update model
2. Generate migration (may need manual editing)
3. Apply migration

### Add Index:

1. Add `index=True` to column in model
2. Generate migration
3. Apply migration

### Add Relationship:

1. Add relationship in both models
2. Generate migration
3. Apply migration

---

## 📝 Example Migration Workflow

```bash
# 1. Make changes to models
# Edit app/models/user.py - add new field

# 2. Generate migration
alembic revision --autogenerate -m "Add bio field to users"

# 3. Review generated migration
# Check alembic/versions/YYYY_MM_DD_HHMM-{revision}_add_bio_field_to_users.py

# 4. Apply migration
alembic upgrade head

# 5. Verify in database
psql -d mamastoria_db -c "\d users"
```

---

## 🚨 Troubleshooting

### Migration Fails:

```bash
# Check current state
alembic current

# Check history
alembic history

# Force stamp to specific version
alembic stamp head
```

### Reset Database:

```bash
# Drop all tables
alembic downgrade base

# Re-create all tables
alembic upgrade head
```

### Manual Migration:

```bash
# Create empty migration
alembic revision -m "Manual migration"

# Edit the generated file manually
# Add upgrade() and downgrade() logic

# Apply
alembic upgrade head
```

---

**Ready to migrate!** Run `alembic upgrade head` to create all tables.
