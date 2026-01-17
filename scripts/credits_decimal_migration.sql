-- Convert credit-related fields to decimal precision
ALTER TABLE users
  ALTER COLUMN kredit TYPE NUMERIC(12,2) USING kredit::numeric,
  ALTER COLUMN kredit SET DEFAULT 0.00,
  ALTER COLUMN balance TYPE NUMERIC(12,2) USING balance::numeric,
  ALTER COLUMN balance SET DEFAULT 0.00;

ALTER TABLE commissions
  ALTER COLUMN kredit TYPE NUMERIC(12,2) USING kredit::numeric,
  ALTER COLUMN kredit SET DEFAULT 0.00;

ALTER TABLE subscription_packages
  ALTER COLUMN bonus_credits TYPE NUMERIC(12,2) USING bonus_credits::numeric,
  ALTER COLUMN bonus_credits SET DEFAULT 0.00;

ALTER TABLE payment_transactions
  ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::numeric,
  ALTER COLUMN amount SET DEFAULT 0.00;

ALTER TABLE transactions
  ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::numeric,
  ALTER COLUMN amount SET DEFAULT 0.00;

ALTER TABLE withdrawals
  ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::numeric,
  ALTER COLUMN amount SET DEFAULT 0.00;
