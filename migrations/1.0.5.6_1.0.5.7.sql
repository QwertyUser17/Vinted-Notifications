BEGIN TRANSACTION;

-- Item links, since OLX offer URLs cannot be rebuilt from the id like Vinted ones
ALTER TABLE items ADD COLUMN url TEXT;

UPDATE parameters
SET value = '1.0.5.7'
WHERE key = 'version';

COMMIT;
