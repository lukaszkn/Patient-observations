-- models/patient_summary.sql

with observations as (

    select * from {{ ref('stg_observations') }}

),

patients as (

    select * from {{ source('public', 'patients') }}

),

patient_summary as (

    select
        p.pat_no,
        p.name,
        p.gender,
        p.birth_date,
        avg(o.total_score) as average_total_score,
        count(o.observation_id) as number_of_observations

    from patients p
    join observations o on p.pat_no = o.patient_id
    group by 1, 2, 3, 4

)

select * from patient_summary
