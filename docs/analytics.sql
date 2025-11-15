-- Detect vendors with high failure rate
SELECT vendor_name, COUNT(*) AS total, AVG(valid::INT) AS accuracy
FROM extractions
WHERE field_name = 'vendor_name'
GROUP BY vendor_name
HAVING AVG(valid::INT) < 0.9;

-- Identify fields with recurrent validation issues
SELECT field_name, COUNT(*) AS failures
FROM extractions
WHERE valid = FALSE
GROUP BY field_name
ORDER BY failures DESC
LIMIT 10;
