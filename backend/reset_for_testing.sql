-- ============================================================
-- ParkEase: Reset to clean state for prototype testing
--
-- Run this to bring the system to a known-good starting state.
-- Historical bookings are set to COMPLETED (not deleted).
-- ============================================================

-- 1. Complete any stale ACTIVE bookings
UPDATE bookings
SET    status = 'COMPLETED',
       active_slot_id = NULL,
       exit_time = NOW()
WHERE  status = 'ACTIVE';

-- 2. Reset all parking slots
UPDATE parking_slots
SET    status = 'AVAILABLE',
       sensor_status = 'EMPTY',
       updated_at = NOW();

-- 3. Reset system state
UPDATE parking_system_state
SET    movement_state = 'IDLE',
       pending_exit_slot_id = NULL,
       entry_vehicle_waiting = FALSE,
       pending_entry_booking_id = NULL,
       updated_at = NOW()
WHERE  id = 1;

-- 4. Verify
SELECT 'SLOTS' AS entity, slot_number, status, sensor_status FROM parking_slots;
SELECT 'STATE' AS entity, movement_state, pending_exit_slot_id, entry_vehicle_waiting, pending_entry_booking_id FROM parking_system_state;
SELECT 'ACTIVE_BOOKINGS' AS entity, COUNT(*) AS count FROM bookings WHERE status = 'ACTIVE';
