from enum import StrEnum


class ContextCategory(StrEnum):
    WEIGHT_CUT = "weight_cut"
    SHORT_NOTICE = "short_notice"
    OPPONENT_CHANGE = "opponent_change"
    WEIGHT_CLASS_CHANGE = "weight_class_change"
    LAYOFF = "layoff"
    RAPID_TURNAROUND = "rapid_turnaround"
    RECENT_DAMAGE = "recent_damage"
    MEDICAL_SUSPENSION = "medical_suspension"
    INJURY = "injury"
    TRAINING_CAMP = "training_camp"
    TRAVEL = "travel"
    ENVIRONMENT = "environment"
    CAREER_STATUS = "career_status"


class ContextLabel(StrEnum):
    MISSED_WEIGHT_CURRENT_FIGHT = "missed_weight_current_fight"
    MISSED_WEIGHT_PREVIOUS_FIGHT = "missed_weight_previous_fight"
    CAREER_WEIGHT_MISS_COUNT = "career_weight_miss_count"
    SHORT_NOTICE_REPLACEMENT = "short_notice_replacement"
    SHORT_NOTICE_DAYS = "short_notice_days"
    OPPONENT_CHANGED = "opponent_changed"
    WEIGHT_CLASS_DEBUT = "weight_class_debut"
    WEIGHT_CLASS_MOVE_UP = "weight_class_move_up"
    WEIGHT_CLASS_MOVE_DOWN = "weight_class_move_down"
    LONG_LAYOFF = "long_layoff"
    RAPID_TURNAROUND = "rapid_turnaround"
    RECENT_KO_LOSS = "recent_ko_loss"
    RECENT_TKO_LOSS = "recent_tko_loss"
    RECENT_SUBMISSION_LOSS = "recent_submission_loss"
    ACTIVE_MEDICAL_SUSPENSION = "active_medical_suspension"
    RECENT_MEDICAL_SUSPENSION = "recent_medical_suspension"
    CONFIRMED_INJURY = "confirmed_injury"
    RECENT_SURGERY = "recent_surgery"
    TRAINING_INTERRUPTION = "training_interruption"
    NEW_TRAINING_CAMP = "new_training_camp"
    NEW_HEAD_COACH = "new_head_coach"
    LONG_DISTANCE_TRAVEL = "long_distance_travel"
    TIMEZONE_DIFFERENCE = "timezone_difference"
    ALTITUDE_CHANGE = "altitude_change"
    RETIREMENT_RETURN = "retirement_return"
    CONTRACT_DISPUTE = "contract_dispute"


class SourceType(StrEnum):
    OFFICIAL_UFC = "official_ufc"
    ATHLETIC_COMMISSION = "athletic_commission"
    FIGHTER_STATEMENT = "fighter_statement"
    COACH_STATEMENT = "coach_statement"
    GYM_STATEMENT = "gym_statement"
    OFFICIAL_EVENT_RESULT = "official_event_result"
    ESTABLISHED_MMA_MEDIA = "established_mma_media"
    GENERAL_MEDIA = "general_media"
    SOCIAL_MEDIA = "social_media"
    PODCAST = "podcast"
    MANUAL_ENTRY = "manual_entry"
    OTHER = "other"


class Direction(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class ExtractionMethod(StrEnum):
    MANUAL = "manual"
    RULE_BASED = "rule_based"
    IMPORTED = "imported"
    LLM_ASSISTED = "llm_assisted"


class ContextMatchStatus(StrEnum):
    MATCHED = "matched"
    UNMATCHED_FIGHTER = "unmatched_fighter"
    UNMATCHED_FIGHT = "unmatched_fight"
    AMBIGUOUS_FIGHTER = "ambiguous_fighter"
    AMBIGUOUS_FIGHT = "ambiguous_fight"
    INVALID_RECORD = "invalid_record"


class ClaimType(StrEnum):
    CONFIRMED_FACT = "confirmed_fact"
    DIRECT_STATEMENT = "direct_statement"
    CREDIBLE_REPORT = "credible_report"
    INFERENCE = "inference"
    RUMOUR = "rumour"
    CONTRADICTED = "contradicted"
