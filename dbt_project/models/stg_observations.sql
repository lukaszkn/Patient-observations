-- models/stg_observations.sql

with source as (

    select * from {{ source('public', 'observations') }}

),

renamed as (

    select
        id as observation_id,
        pat_no as patient_id,
        timestamp as observed_at,
        total_score,
        readings

    from source

)

select * from renamed
