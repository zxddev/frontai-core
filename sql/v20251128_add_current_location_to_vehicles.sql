-- Add current_location column to vehicles_v2 table
-- This column is required for vehicle location tracking and was missing in the schema

ALTER TABLE operational_v2.vehicles_v2 
ADD COLUMN IF NOT EXISTS current_location GEOGRAPHY(POINT, 4326);

-- Create index for spatial queries
CREATE INDEX IF NOT EXISTS idx_vehicles_v2_location 
ON operational_v2.vehicles_v2 USING GIST (current_location);
