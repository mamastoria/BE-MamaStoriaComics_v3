-- Create admin user SQL script
-- Password hash for 'admin123': $2b$12$JsjZK5R5VTSbAJqucDHe5.MnUJnkBNrD0OHqK7snDgCNmWnGzc6mW

-- Check if user exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE phone_number = '+6281234567890') THEN
        -- Update existing user to admin
        UPDATE users 
        SET role = 'admin', 
            kredit = 999999,
            is_verified = true
        WHERE phone_number = '+6281234567890';
        RAISE NOTICE 'User updated to admin role';
    ELSE
        -- Create new admin user
        INSERT INTO users (
            phone_number, 
            password, 
            full_name, 
            kredit, 
            is_verified, 
            referral_code_id, 
            role
        ) VALUES (
            '+6281234567890',
            '$2b$12$JsjZK5R5VTSbAJqucDHe5.MnUJnkBNrD0OHqK7snDgCNmWnGzc6mW',
            'Admin Dashboard',
            999999,
            true,
            'ADMIN001',
            'admin'
        );
        RAISE NOTICE 'Admin user created';
    END IF;
END $$;

-- Verify
SELECT id_users, phone_number, full_name, role, kredit, is_verified 
FROM users 
WHERE phone_number = '+6281234567890';
