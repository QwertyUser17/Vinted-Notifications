BEGIN TRANSACTION;

-- Banwords that apply to a single query, on top of the global ones
ALTER TABLE queries ADD COLUMN banwords TEXT;

UPDATE parameters
SET value = '1.0.5.5'
WHERE key = 'version';

COMMIT;
