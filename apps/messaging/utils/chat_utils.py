def check_room_access(user, room):
    """Check if user has access to room based on case participants."""
    case = room.case
    return user == case.patient.user or (case.doctor and user == case.doctor.user)