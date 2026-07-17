from app.context.enums import ContextCategory, ContextLabel, SourceType

CONTEXT_LABEL_REGISTRY: dict[ContextCategory, set[ContextLabel]] = {
    ContextCategory.WEIGHT_CUT: {
        ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT,
        ContextLabel.MISSED_WEIGHT_PREVIOUS_FIGHT,
        ContextLabel.CAREER_WEIGHT_MISS_COUNT,
    },
    ContextCategory.SHORT_NOTICE: {ContextLabel.SHORT_NOTICE_REPLACEMENT, ContextLabel.SHORT_NOTICE_DAYS},
    ContextCategory.OPPONENT_CHANGE: {ContextLabel.OPPONENT_CHANGED},
    ContextCategory.WEIGHT_CLASS_CHANGE: {
        ContextLabel.WEIGHT_CLASS_DEBUT,
        ContextLabel.WEIGHT_CLASS_MOVE_UP,
        ContextLabel.WEIGHT_CLASS_MOVE_DOWN,
    },
    ContextCategory.LAYOFF: {ContextLabel.LONG_LAYOFF},
    ContextCategory.RAPID_TURNAROUND: {ContextLabel.RAPID_TURNAROUND},
    ContextCategory.RECENT_DAMAGE: {
        ContextLabel.RECENT_KO_LOSS,
        ContextLabel.RECENT_TKO_LOSS,
        ContextLabel.RECENT_SUBMISSION_LOSS,
    },
    ContextCategory.MEDICAL_SUSPENSION: {
        ContextLabel.ACTIVE_MEDICAL_SUSPENSION,
        ContextLabel.RECENT_MEDICAL_SUSPENSION,
    },
    ContextCategory.INJURY: {ContextLabel.CONFIRMED_INJURY, ContextLabel.RECENT_SURGERY},
    ContextCategory.TRAINING_CAMP: {
        ContextLabel.TRAINING_INTERRUPTION,
        ContextLabel.NEW_TRAINING_CAMP,
        ContextLabel.NEW_HEAD_COACH,
    },
    ContextCategory.TRAVEL: {ContextLabel.LONG_DISTANCE_TRAVEL, ContextLabel.TIMEZONE_DIFFERENCE},
    ContextCategory.ENVIRONMENT: {ContextLabel.ALTITUDE_CHANGE},
    ContextCategory.CAREER_STATUS: {ContextLabel.RETIREMENT_RETURN, ContextLabel.CONTRACT_DISPUTE},
}

SOURCE_RELIABILITY: dict[SourceType, float] = {
    SourceType.ATHLETIC_COMMISSION: 0.98,
    SourceType.OFFICIAL_UFC: 0.96,
    SourceType.OFFICIAL_EVENT_RESULT: 0.98,
    SourceType.FIGHTER_STATEMENT: 0.90,
    SourceType.COACH_STATEMENT: 0.87,
    SourceType.GYM_STATEMENT: 0.85,
    SourceType.ESTABLISHED_MMA_MEDIA: 0.80,
    SourceType.GENERAL_MEDIA: 0.70,
    SourceType.PODCAST: 0.65,
    SourceType.SOCIAL_MEDIA: 0.55,
    SourceType.MANUAL_ENTRY: 0.75,
    SourceType.OTHER: 0.40,
}

HALF_LIFE_DAYS: dict[ContextCategory, int | None] = {
    ContextCategory.WEIGHT_CUT: 365,
    ContextCategory.SHORT_NOTICE: None,
    ContextCategory.OPPONENT_CHANGE: None,
    ContextCategory.WEIGHT_CLASS_CHANGE: 365,
    ContextCategory.LAYOFF: None,
    ContextCategory.RAPID_TURNAROUND: 90,
    ContextCategory.RECENT_DAMAGE: 180,
    ContextCategory.MEDICAL_SUSPENSION: None,
    ContextCategory.INJURY: 90,
    ContextCategory.TRAINING_CAMP: 180,
    ContextCategory.TRAVEL: None,
    ContextCategory.ENVIRONMENT: None,
    ContextCategory.CAREER_STATUS: 365,
}

LABEL_ADJUSTMENT_CAPS: dict[ContextLabel, float] = {
    ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT: 0.015,
    ContextLabel.SHORT_NOTICE_REPLACEMENT: 0.020,
    ContextLabel.OPPONENT_CHANGED: 0.005,
    ContextLabel.WEIGHT_CLASS_DEBUT: 0.010,
    ContextLabel.LONG_LAYOFF: 0.015,
    ContextLabel.RAPID_TURNAROUND: 0.010,
    ContextLabel.RECENT_KO_LOSS: 0.012,
    ContextLabel.ACTIVE_MEDICAL_SUSPENSION: 0.0,
    ContextLabel.CONFIRMED_INJURY: 0.020,
    ContextLabel.NEW_TRAINING_CAMP: 0.005,
    ContextLabel.TIMEZONE_DIFFERENCE: 0.005,
    ContextLabel.ALTITUDE_CHANGE: 0.005,
}
