-- SQL Window Function Examples for Patient Data

-- Before running these queries, ensure you have loaded the data into PostgreSQL
-- by running the `load_data_to_postgres.py` script first.


-- ======================================================================================
-- Query 1: Calculate Score Change Between Observations using LAG()
-- ======================================================================================
-- This query uses the LAG() window function to find the previous total_score for each patient,
-- ordered by the observation timestamp. It then calculates the difference to see if the
-- patient's condition is improving (negative change) or worsening (positive change).

SELECT
    p.name,
    o.timestamp,
    o.total_score,
    LAG(o.total_score, 1, 0) OVER (PARTITION BY o.pat_no ORDER BY o.timestamp) AS previous_score,
    o.total_score - LAG(o.total_score, 1, 0) OVER (PARTITION BY o.pat_no ORDER BY o.timestamp) AS score_change
FROM
    observations o
JOIN
    patients p ON o.pat_no = p.pat_no
ORDER BY
    p.name,
    o.timestamp;


-- ======================================================================================
-- Query 2: Rank Patient Observations by Score using RANK() and DENSE_RANK()
-- ======================================================================================
-- This query ranks each patient's observations based on their total_score in descending order.
-- RANK() gives the same rank to rows with the same score, creating gaps in the sequence for the next rank.
-- DENSE_RANK() also gives the same rank to tied rows but does not create gaps.

SELECT
    p.name,
    o.timestamp,
    o.total_score,
    RANK() OVER (PARTITION BY o.pat_no ORDER BY o.total_score DESC) AS score_rank,
    DENSE_RANK() OVER (PARTITION BY o.pat_no ORDER BY o.total_score DESC) AS score_dense_rank
FROM
    observations o
JOIN
    patients p ON o.pat_no = p.pat_no
ORDER BY
    p.name,
    o.total_score DESC;


-- ======================================================================================
-- Query 3: Calculate a 3-Observation Moving Average Score using AVG()
-- ======================================================================================
-- This query calculates a "moving average" of the total_score for each patient over their
-- last 3 observations (the current row and the two preceding rows). This can help smooth
-- out short-term fluctuations and identify trends.

SELECT
    p.name,
    o.timestamp,
    o.total_score,
    AVG(o.total_score) OVER (
        PARTITION BY o.pat_no
        ORDER BY o.timestamp
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS moving_avg_score_3_obs
FROM
    observations o
JOIN
    patients p ON o.pat_no = p.pat_no
ORDER BY
    p.name,
    o.timestamp;
