"""Personalized cinematic shot templates for snowboarding, camping, and outdoor activities.

================================================================================
WHY THESE TEMPLATES EXIST: REDESIGN RATIONALE
================================================================================

The original CINEMATIC_TEMPLATES were designed for generic "extreme sports" - they
assumed halfpipe snowboarding, professional skateboarding, and urban exploration.
But that's not what YOU actually do.

YOUR ACTUAL ACTIVITIES (the ones worth filming):
- Snowboarding on regular hills (not halfpipe) - carving, terrain park features
- Camping and nature exploration - scenic walks, landscape shots
- Mountain biking on trails - technical riding, flow sections
- Ripstick (your brother) - smooth cruising, sidewalk carving
- General action: running, jumping, playing around

THE PROBLEM WITH GENERIC TEMPLATES:
- Halfpipe presets: Wrong for hill snowboarding - too tight, wrong angles
- Skateboard speeds: Too fast for ripstick, which is slower and smoother
- Urban orbit shots: Don't make sense in open mountain terrain
- Aggressive follow: Too jerky for scenic nature shots

THE REDESIGN APPROACH:
Each profile and template is tuned to match ACTUAL SPEEDS and ACTUAL CONTEXTS:
- Snowboard terrain park: Medium distance, can see rails/jumps, not too close
- Snowboard hill run: Wider for scenic context, higher for terrain visibility
- Ripstick: Slower, closer, more intimate (it's smooth, not aggressive)
- Mountain biking: Fast enough for downhill, lookahead for obstacles
- Nature explore: Slow, smooth, cinematic - this is about the scenery, not action

================================================================================
HOW THIS DIFFERS FROM GENERIC TEMPLATES
================================================================================

                    GENERIC              PERSONALIZED (this file)
                    -------              --------------------------
Snowboarding        Halfpipe (tight)     Hill runs (wide scenic)
                    15m/s speed          8-12m/s (real carving speed)

Skateboarding       Street tricks        Ripstick cruising
                    Fast/aggressive      Slow/smooth/flow

Biking              BMX/tricks           Mountain trail riding
                    Urban                Natural terrain, obstacle avoidance

Nature              None (ignored)       First-class citizen
                                         Camping/hiking as main activity

================================================================================
WHEN TO USE EACH TEMPLATE: QUICK REFERENCE
================================================================================

SNOWBOARDING:
- "snowboard_terrain_park" - Rails, boxes, small jumps at terrain park
- "snowboard_hill_run" - Carving down slopes, tree runs, general riding
- "snowboard_jump" - Capturing jump arcs, height-locked tracking

OTHER ACTIVITIES:
- "ripstick_flow" - Brother on ripstick, smooth sidewalk cruising
- "mountain_bike_trail" - Technical trail riding, downhill sections
- "run_and_jump" - General running, parkour, jumping over things

CAMPING & NATURE:
- "nature_explore" - Walking through scenery, camping activities
- "nature_orbit" - Wide scenic landscape shots, establishing context

UNIVERSAL:
- "action_jump" - Any sport jump (snowboard, bike, running leap)
- "orbit_close" - Portrait-style orbits for any activity
- "orbit_wide" - Context shots showing environment
- "follow_close" - Intimate action following
- "reveal_hero" - Dramatic entrance shots
- "top_down_dynamic" - Bird's eye view tracking
"""

from avatar.mcp_server.tools.cinematic_shots import (
    ShotTemplate, ShotType, MotionCurveType, MotionProfile, SPORT_PROFILES
)

# ==============================================================================
# PERSONALIZED MOTION PROFILES
# ==============================================================================
# These profiles define the PHYSICAL CONSTRAINTS for each activity type.
# They answer: How fast? How close? How predictive?
#
# KEY PARAMETERS EXPLAINED:
# - max_speed_m_s: Maximum drone speed needed to track this activity
# - max_accel_m_s2: How aggressively drone can accelerate (lower = smoother)
# - lookahead_s: Prediction time (higher = anticipate turns/obstacles better)
# - distance_m: How far from subject (closer = intimate, wider = context)
# - height_offset_m: Drone height above subject (affects perspective)
# - lateral_offset_m: Side distance for angled shots
# ==============================================================================

PERSONAL_PROFILES = {
    # -----------------------------------------------------------------------------
    # SNOWBOARD TERRAIN PARK
    # -----------------------------------------------------------------------------
    # USE WHEN: Rails, boxes, jumps, any freestyle terrain park features
    # WHY THIS PROFILE: Terrain park needs medium-wide framing to see features
    # coming. Too close and you miss the rail approach. Too far and it's boring.
    # Speed is moderate (8 m/s) because park riding isn't about max speed -
    # it's about control and tricks.
    # -----------------------------------------------------------------------------
    "snowboard_terrain_park": MotionProfile(
        name="Snowboard Terrain Park",
        max_speed_m_s=8.0,  # Moderate speed for park features
        max_accel_m_s2=2.0,
        lookahead_s=0.25,  # Medium prediction for jump landing
        distance_m=12.0,   # Wide enough to see features
        height_offset_m=6.0,  # Above jumps/rails for visibility
        lateral_offset_m=8.0,
        description="Optimized for terrain park features - rails, boxes, small jumps"
    ),

    # -----------------------------------------------------------------------------
    # SNOWBOARD HILL RUN
    # -----------------------------------------------------------------------------
    # USE WHEN: Carving down slopes, tree runs, wide open groomers
    # WHY THIS PROFILE: Hill runs need WIDE shots for scenic mountain context.
    # You're not in a pipe - you're on a mountain. The shot should show the
    # mountain. Higher altitude (8m) gives terrain visibility - you can see
    # the slope falling away. Faster speed (12 m/s) matches carving speed.
    # -----------------------------------------------------------------------------
    "snowboard_hill_run": MotionProfile(
        name="Snowboard Hill Run",
        max_speed_m_s=12.0,  # Match carving speed
        max_accel_m_s2=2.5,
        lookahead_s=0.3,   # Higher for downhill prediction
        distance_m=15.0,     # Wider for scenic mountain context
        height_offset_m=8.0, # Higher for terrain visibility
        lateral_offset_m=10.0,
        description="Wide scenic shots for carving down slopes and tree runs"
    ),

    # -----------------------------------------------------------------------------
    # RIPSTICK FLOW
    # -----------------------------------------------------------------------------
    # USE WHEN: Brother on ripstick, smooth sidewalk cruising, carving
    # WHY THIS PROFILE: Ripstick is NOT a skateboard. It's slower (4 m/s max),
    # smoother, more flowing. The profile reflects this - closer distance (6m)
    # for intimacy, lower height (2.5m) for eye-level perspective. This is
    # casual cruising, not aggressive street skating.
    # -----------------------------------------------------------------------------
    "ripstick_flow": MotionProfile(
        name="Ripstick Cruising",
        max_speed_m_s=4.0,   # Ripstick is slower than skateboard
        max_accel_m_s2=1.2,
        lookahead_s=0.2,
        distance_m=6.0,      # Close and personal
        height_offset_m=2.5, # Eye level-ish
        lateral_offset_m=4.0,
        description="Smooth following for ripstick cruising and carving"
    ),

    # -----------------------------------------------------------------------------
    # MOUNTAIN BIKE TRAIL
    # -----------------------------------------------------------------------------
    # USE WHEN: Technical trail riding, downhill, flow trails
    # WHY THIS PROFILE: Mountain biking can be FAST (10 m/s downhill) with
    # sudden obstacles. High lookahead (0.35s) anticipates trail features.
    # Medium height (4m) clears handlebars while keeping rider in context.
    # Wide distance (12m) captures the trail environment.
    # -----------------------------------------------------------------------------
    "mountain_bike_trail": MotionProfile(
        name="Mountain Bike Trail",
        max_speed_m_s=10.0,  # Can be fast on downhill
        max_accel_m_s2=2.5,
        lookahead_s=0.35,    # High for trail obstacles
        distance_m=12.0,     # Wide for trail context
        height_offset_m=4.0, # Above handlebars level
        lateral_offset_m=6.0,
        description="Trail following with obstacle anticipation"
    ),

    # -----------------------------------------------------------------------------
    # NATURE EXPLORE
    # -----------------------------------------------------------------------------
    # USE WHEN: Camping, hiking, nature walks, scenic exploration
    # WHY THIS PROFILE: This is SLOW and CINEMATIC. Speed is only 3 m/s -
    # you're walking, not racing. Very smooth acceleration (1.0) for glide-like
    # movement. Medium distance (8m) balances intimacy with landscape context.
    # This is about enjoying scenery, not action sports.
    # -----------------------------------------------------------------------------
    "nature_explore": MotionProfile(
        name="Nature Exploration",
        max_speed_m_s=3.0,   # Slow for scenic shots
        max_accel_m_s2=1.0,  # Very smooth
        lookahead_s=0.2,
        distance_m=8.0,      # Medium for intimacy
        height_offset_m=4.0,   # Slight elevation for landscapes
        lateral_offset_m=5.0,
        description="Slow cinematic movement through natural scenery"
    ),

    # -----------------------------------------------------------------------------
    # ACTION JUMP (UNIVERSAL)
    # -----------------------------------------------------------------------------
    # USE WHEN: Any jump - snowboard kickers, bike drops, running leaps
    # WHY THIS PROFILE: Jumps need height-locked tracking to capture the full
    # arc. Lateral offset is 0 (direct follow) so the subject stays centered
    # through the jump. Fast speed (10 m/s) handles jump trajectory. This works
    # across ALL activities - it's jump physics, not sport-specific.
    # -----------------------------------------------------------------------------
    "action_jump": MotionProfile(
        name="Action Jump Tracking",
        max_speed_m_s=10.0,
        max_accel_m_s2=3.0,
        lookahead_s=0.3,     # Track through jump arc
        distance_m=10.0,
        height_offset_m=3.0,
        lateral_offset_m=0.0,  # Direct follow for jump
        description="Height-locked tracking for jumps - snowboard, bike, or running"
    ),
}

# ==============================================================================
# PERSONALIZED SHOT TEMPLATES
# ==============================================================================
# These are the ACTUAL SHOTS you can call. Each template uses the motion
# profiles above plus additional cinematic parameters:
#
# - shot_type: The camera movement style (orbit, follow, etc.)
# - duration_s: How long the shot lasts
# - motion_curve: Easing style (linear = constant, ease_in_out = smooth start/end)
# - gimbal_pitch_offset: Camera angle (negative = look down at subject)
# - predictive_frames: How much to anticipate subject movement
# - height_lock: Whether to maintain altitude during jumps
# - quality_thresholds: Precision requirements for this shot type
# ==============================================================================

PERSONAL_TEMPLATES = {
    # ==========================================================================
    # GENERAL PURPOSE TEMPLATES
    # ==========================================================================
    # These work across ALL activities - keep these in your back pocket
    # for any situation that doesn't need activity-specific tuning.
    # ==========================================================================

    # --------------------------------------------------------------------------
    # CLOSE ORBIT
    # --------------------------------------------------------------------------
    # USE WHEN: Portrait-style shots, showing the subject in their environment
    # COMPARED TO WIDE ORBIT: Much closer (8m vs 20m), more intimate
    # MOTION: Ease in/out for smooth start and stop
    # BEST FOR: Quick establishing shots of the person
    # --------------------------------------------------------------------------
    "orbit_close": ShotTemplate(
        name="Close Orbit (Cinematic)",
        shot_type=ShotType.ORBIT,
        distance_m=8.0,
        height_offset_m=3.0,
        speed_m_s=2.0,
        duration_s=15.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
    ),

    # --------------------------------------------------------------------------
    # WIDE ORBIT
    # --------------------------------------------------------------------------
    # USE WHEN: Showing the full scene, landscape context, "where are they"
    # COMPARED TO CLOSE ORBIT: Much wider (20m), higher (8m), shows environment
    # MOTION: Linear for constant rotation speed
    # BEST FOR: Opening shots, scenic reveals
    # --------------------------------------------------------------------------
    "orbit_wide": ShotTemplate(
        name="Wide Orbit (Context)",
        shot_type=ShotType.ORBIT,
        distance_m=20.0,
        height_offset_m=8.0,
        speed_m_s=4.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-30.0,
    ),

    # --------------------------------------------------------------------------
    # CLOSE FOLLOW
    # --------------------------------------------------------------------------
    # USE WHEN: Intimate action following, "you are there" feeling
    # COMPARED TO DYNAMIC FOLLOW: Closer (6m), tighter framing
    # MOTION: Ease in/out for smooth tracking
    # BEST FOR: Close action, personal perspective
    # --------------------------------------------------------------------------
    "follow_close": ShotTemplate(
        name="Close Follow (Action)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=6.0,
        height_offset_m=2.5,
        lateral_offset_m=2.0,
        speed_m_s=8.0,
        duration_s=30.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-10.0,
        predictive_frames=1.5,
    ),

    # --------------------------------------------------------------------------
    # HERO REVEAL
    # --------------------------------------------------------------------------
    # USE WHEN: Dramatic entrances, "here I am" moments
    # SHOT TYPE: Ascent from ground level to reveal subject
    # MOTION: Ease out (decelerate as reaching final position)
    # BEST FOR: Starting videos, introducing the subject dramatically
    # --------------------------------------------------------------------------
    "reveal_hero": ShotTemplate(
        name="Hero Reveal",
        shot_type=ShotType.REVEAL_ASCENT,
        distance_m=0.0,
        height_offset_m=20.0,
        speed_m_s=2.0,
        duration_s=8.0,
        motion_curve=MotionCurveType.EASE_OUT,
        gimbal_pitch_offset=0.0,
    ),

    # --------------------------------------------------------------------------
    # TOP-DOWN CONTEXT
    # --------------------------------------------------------------------------
    # USE WHEN: Bird's eye view tracking, pattern recognition
    # SHOT TYPE: Directly overhead, tracking subject movement
    # GIMBAL: -90 degrees = straight down
    # BEST FOR: Showing movement patterns, trails, geometry
    # --------------------------------------------------------------------------
    "top_down_dynamic": ShotTemplate(
        name="Top-Down Context",
        shot_type=ShotType.TOP_DOWN,
        distance_m=0.0,
        height_offset_m=15.0,
        speed_m_s=3.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-90.0,
    ),

    # ==========================================================================
    # SNOWBOARDING TEMPLATES
    # ==========================================================================
    # These are tuned SPECIFICALLY for snowboarding activities.
    # Use these instead of generic templates for snow footage.
    # ==========================================================================

    # --------------------------------------------------------------------------
    # TERRAIN PARK
    # --------------------------------------------------------------------------
    # USE WHEN: Rails, boxes, jumps at terrain park
    # PROFILE: Uses snowboard_terrain_park motion profile
    # VS GENERIC: Not as tight as halfpipe presets, shows approach/landing
    # BEST FOR: Park laps, feature hitting, freestyle
    # --------------------------------------------------------------------------
    "snowboard_terrain_park": ShotTemplate(
        name="Terrain Park (Rails & Jumps)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=PERSONAL_PROFILES["snowboard_terrain_park"].distance_m,
        height_offset_m=PERSONAL_PROFILES["snowboard_terrain_park"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["snowboard_terrain_park"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["snowboard_terrain_park"].max_speed_m_s,
        duration_s=20.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
        predictive_frames=PERSONAL_PROFILES["snowboard_terrain_park"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # HILL RUN
    # --------------------------------------------------------------------------
    # USE WHEN: Carving, tree runs, general slope riding
    # PROFILE: Uses snowboard_hill_run motion profile
    # VS TERRAIN PARK: Wider (15m), higher (8m), shows mountain context
    # VS GENERIC: Not a halfpipe shot - this is for open mountain
    # BEST FOR: Scenic riding, powder runs, carving shots
    # --------------------------------------------------------------------------
    "snowboard_hill_run": ShotTemplate(
        name="Hill Run (Scenic Carving)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=PERSONAL_PROFILES["snowboard_hill_run"].distance_m,
        height_offset_m=PERSONAL_PROFILES["snowboard_hill_run"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["snowboard_hill_run"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["snowboard_hill_run"].max_speed_m_s,
        duration_s=45.0,
        motion_curve=MotionCurveType.LINEAR,  # Constant speed for smooth carving
        gimbal_pitch_offset=-25.0,
        predictive_frames=PERSONAL_PROFILES["snowboard_hill_run"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # SNOWBOARD JUMP
    # --------------------------------------------------------------------------
    # USE WHEN: Capturing jump arcs, kickers, air time
    # SPECIAL: Height-locked tracking maintains altitude during jump
    # VS GENERIC: Tuned for snowboard jump speeds and heights
    # QUALITY: Tight thresholds for precise jump framing
    # BEST FOR: Jump shots, air time, grab tricks
    # --------------------------------------------------------------------------
    "snowboard_jump": ShotTemplate(
        name="Snowboard Jump Tracking",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=10.0,
        height_offset_m=3.0,
        speed_m_s=10.0,
        duration_s=8.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-15.0,
        height_lock=True,
        predictive_frames=0.3,
        quality_thresholds={
            "max_position_error_m": 1.0,
            "max_height_error_m": 0.3,
            "min_framing_score": 0.8,
        },
    ),

    # ==========================================================================
    # OTHER ACTIVITIES TEMPLATES
    # ==========================================================================
    # Ripstick, mountain biking, general action - activities beyond snowboarding
    # ==========================================================================

    # --------------------------------------------------------------------------
    # RIPSTICK CRUISING
    # --------------------------------------------------------------------------
    # USE WHEN: Brother on ripstick, smooth sidewalk cruising
    # PROFILE: Uses ripstick_flow motion profile
    # VS SKATEBOARD: Slower (4 m/s), closer (6m), smoother
    # VS GENERIC: Not aggressive street skating - this is flow
    # BEST FOR: Ripstick sessions, smooth carving, casual riding
    # --------------------------------------------------------------------------
    "ripstick_flow": ShotTemplate(
        name="Ripstick Cruising",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=PERSONAL_PROFILES["ripstick_flow"].distance_m,
        height_offset_m=PERSONAL_PROFILES["ripstick_flow"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["ripstick_flow"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["ripstick_flow"].max_speed_m_s,
        duration_s=30.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-10.0,
        predictive_frames=PERSONAL_PROFILES["ripstick_flow"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # MOUNTAIN BIKE TRAIL
    # --------------------------------------------------------------------------
    # USE WHEN: Technical trail riding, flow trails, downhill
    # PROFILE: Uses mountain_bike_trail motion profile
    # VS GENERIC: Anticipates obstacles (0.35s lookahead), trail context
    # VS ROAD BIKING: Accounts for terrain, not just speed
    # BEST FOR: MTB rides, trail sessions, technical sections
    # --------------------------------------------------------------------------
    "mountain_bike_trail": ShotTemplate(
        name="Mountain Bike Trail Follow",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=PERSONAL_PROFILES["mountain_bike_trail"].distance_m,
        height_offset_m=PERSONAL_PROFILES["mountain_bike_trail"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["mountain_bike_trail"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["mountain_bike_trail"].max_speed_m_s,
        duration_s=60.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
        predictive_frames=PERSONAL_PROFILES["mountain_bike_trail"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # NATURE EXPLORATION
    # --------------------------------------------------------------------------
    # USE WHEN: Camping, hiking, walking through nature
    # PROFILE: Uses nature_explore motion profile
    # VS ACTION TEMPLATES: Much slower (3 m/s), longer duration (2 min)
    # VS GENERIC: Actually exists (generic templates ignore nature activities)
    # BEST FOR: Camping trips, nature walks, scenic exploration
    # --------------------------------------------------------------------------
    "nature_explore": ShotTemplate(
        name="Nature Walk / Camping",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=PERSONAL_PROFILES["nature_explore"].distance_m,
        height_offset_m=PERSONAL_PROFILES["nature_explore"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["nature_explore"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["nature_explore"].max_speed_m_s,
        duration_s=120.0,  # Long duration for exploration
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-15.0,
        predictive_frames=PERSONAL_PROFILES["nature_explore"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # SCENIC NATURE ORBIT
    # --------------------------------------------------------------------------
    # USE WHEN: Wide landscape shots, establishing scenery context
    # VS REGULAR ORBIT: Wider (25m), higher (12m), slower (2 m/s)
    # VS NATURE_EXPLORE: This orbits around a point, not following a subject
    # BEST FOR: Landscape cinematics, campsite establishing shots
    # --------------------------------------------------------------------------
    "nature_orbit": ShotTemplate(
        name="Scenic Orbit (Landscape)",
        shot_type=ShotType.ORBIT,
        distance_m=25.0,     # Very wide for landscapes
        height_offset_m=12.0,
        speed_m_s=2.0,       # Slow for cinematic feel
        duration_s=30.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-35.0,  # Look down at landscape
    ),

    # ==========================================================================
    # UNIVERSAL ACTION TEMPLATES
    # ==========================================================================
    # These work across ALL sports for specific shot types (jumps, etc.)
    # ==========================================================================

    # --------------------------------------------------------------------------
    # ACTION JUMP (ANY SPORT)
    # --------------------------------------------------------------------------
    # USE WHEN: Any jump - snowboard, bike, running, whatever
    # PROFILE: Uses action_jump motion profile
    # SPECIAL: Height-locked tracking for jump arc capture
    # VS SPORT-SPECIFIC: Generic jump physics, works everywhere
    # BEST FOR: Quick jump shots when you don't want to pick a specific sport
    # --------------------------------------------------------------------------
    "action_jump": ShotTemplate(
        name="Action Jump (Any Sport)",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=PERSONAL_PROFILES["action_jump"].distance_m,
        height_offset_m=PERSONAL_PROFILES["action_jump"].height_offset_m,
        lateral_offset_m=PERSONAL_PROFILES["action_jump"].lateral_offset_m,
        speed_m_s=PERSONAL_PROFILES["action_jump"].max_speed_m_s,
        duration_s=5.0,  # Short for jump duration
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-15.0,
        height_lock=True,
        predictive_frames=PERSONAL_PROFILES["action_jump"].lookahead_s,
    ),

    # --------------------------------------------------------------------------
    # RUN & JUMP TRACKING
    # --------------------------------------------------------------------------
    # USE WHEN: Running, parkour, general athletic movement
    # VS ACTION_JUMP: Follows dynamically instead of height-lock
    # VS OTHER TEMPLATES: Tuned for running speed (6 m/s)
    # BEST FOR: Trail running, parkour, general action
    # --------------------------------------------------------------------------
    "run_and_jump": ShotTemplate(
        name="Run & Jump Tracking",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=8.0,
        height_offset_m=3.0,
        speed_m_s=6.0,  # Running speed
        duration_s=15.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-15.0,
        predictive_frames=0.2,
    ),
}

# ==============================================================================
# TEMPLATE CATEGORIES FOR UI GROUPING
# ==============================================================================
# These categories organize templates in the UI for easier selection.
# They group related activities together so you can quickly find
# the right template for your current situation.
# ==============================================================================

TEMPLATE_CATEGORIES = {
    "General": ["orbit_close", "orbit_wide", "follow_close", "reveal_hero", "top_down_dynamic"],
    "Snowboarding": ["snowboard_terrain_park", "snowboard_hill_run", "snowboard_jump"],
    "Other Activities": ["ripstick_flow", "mountain_bike_trail", "run_and_jump"],
    "Camping & Nature": ["nature_explore", "nature_orbit"],
    "Universal": ["action_jump"],
}


# ==============================================================================
# PUBLIC API FUNCTIONS
# ==============================================================================

def get_personal_template(name: str) -> ShotTemplate:
    """Get a personalized template by name.

    Args:
        name: Template name (e.g., "snowboard_hill_run", "nature_orbit")

    Returns:
        ShotTemplate instance or None if not found

    Example:
        template = get_personal_template("snowboard_terrain_park")
    """
    return PERSONAL_TEMPLATES.get(name)


def list_personal_templates() -> list:
    """List all personalized template names with categories.

    Returns:
        List of dicts with 'name' and 'category' keys for UI display

    Example:
        templates = list_personal_templates()
        # Returns: [{"name": "snowboard_hill_run", "category": "Snowboarding"}, ...]
    """
    result = []
    for category, templates in TEMPLATE_CATEGORIES.items():
        for t in templates:
            result.append({"name": t, "category": category})
    return result
