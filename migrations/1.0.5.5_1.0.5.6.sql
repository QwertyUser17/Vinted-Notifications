BEGIN TRANSACTION;

-- Items hidden from the web UI. They stay in the table so they are not notified again.
ALTER TABLE items ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0;

UPDATE parameters
SET value = '1.0.5.6'
WHERE key = 'version';

COMMIT;
