USE specs_schema;


SHOW TABLES;

SELECT * FROM products limit 5;

SELECT * FROM product_specs limit 5;


SELECT 
    p.id AS product_id,
    p.sku,
    MAX(CASE WHEN ps.key = 'Width' THEN ps.value END)  AS Width,
    MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) AS Height,
    MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) AS Weight,
    MAX(CASE WHEN ps.key = 'Length' THEN ps.value END) AS Length
FROM products p
LEFT JOIN product_specs ps ON p.id = ps.product_id
GROUP BY p.id, p.sku;

SELECT 
    p.id AS product_id,
    p.sku,
    MAX(CASE WHEN ps.key = 'Width' THEN ps.value END)  AS Width,
    MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) AS Height,
    MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) AS Weight,
    MAX(CASE WHEN ps.key = 'Length' THEN ps.value END) AS Length,
    CASE
        WHEN
            MAX(CASE WHEN ps.key = 'Width' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Length' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Width' THEN ps.value END) IN ('0', 'N/A') OR
            MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) IN ('0', 'N/A') OR
            MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) IN ('0', 'N/A') OR
            MAX(CASE WHEN ps.key = 'Length' THEN ps.value END) IN ('0', 'N/A')
        THEN 'INVALID'
        ELSE 'VALID'
    END AS Spec_Status
FROM products p
LEFT JOIN product_specs ps ON p.id = ps.product_id
GROUP BY p.id, p.sku;


SELECT * FROM (
    SELECT 
    p.id AS product_id,
    p.sku,
    MAX(CASE WHEN ps.key = 'Width' THEN ps.value END)  AS Width,
    MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) AS Height,
    MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) AS Weight,
    CASE
        WHEN
            MAX(CASE WHEN ps.key = 'Width' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) IS NULL OR
            MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) IS NULL OR
            
            MAX(CASE WHEN ps.key = 'Width' THEN ps.value END) IN ('0', 'N/A') OR
            MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) IN ('0', 'N/A') OR
            MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) IN ('0', 'N/A')
        THEN 'INVALID'
        ELSE 'VALID'
    END AS Spec_Status
FROM products p
LEFT JOIN product_specs ps ON p.id = ps.product_id
GROUP BY p.id, p.sku
) AS product_data
WHERE Spec_Status = 'INVALID';

select

SELECT 
    p.sku,
    MAX(CASE WHEN ps.key = 'Width'  THEN ps.value END) AS Width,
    MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) AS Height,
    MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) AS Weight
FROM products p
LEFT JOIN product_specs ps ON p.id = ps.product_id
GROUP BY p.id, p.sku
HAVING 
    Width  IN ('0', 'N/A') OR
    Height IN ('0', 'N/A') OR
    Weight IN ('0', 'N/A');


SELECT 
    p.id AS product_id,
    p.sku,
    MAX(CASE WHEN ps.key = 'Width'  THEN ps.value END) AS Width,
    MAX(CASE WHEN ps.key = 'Height' THEN ps.value END) AS Height,
    MAX(CASE WHEN ps.key = 'Weight' THEN ps.value END) AS Weight
FROM products p
LEFT JOIN product_specs ps ON p.id = ps.product_id
GROUP BY p.id, p.sku
HAVING 
    Width  IN ('0', 'N/A') OR
    Height IN ('0', 'N/A') OR
    Weight IN ('0', 'N/A');
