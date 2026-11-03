"""Conservative reservations and measured usage, in integer micro-USD."""

from vidoclens.contracts.teacher import TeacherPriceCard, TeacherProfile, TeacherUsage


def _micro(nano: int, batch: bool) -> int:
    divisor = 2000 if batch else 1000
    return (nano + divisor - 1) // divisor


def reserve_cost(profile: TeacherProfile, card: TeacherPriceCard, *, batch=False) -> int:
    if profile.model_snapshot != card.model_snapshot:
        raise ValueError("price card belongs to another model")
    if profile.max_output_tokens > card.max_output_tokens:
        raise ValueError("output cap exceeds priced model limit")
    # Reserve the full documented input limit at the most expensive context tier.
    # No guessed tokenizer/image-token count is used as a billing safety boundary.
    nano = card.max_input_tokens * card.input_nano_usd * card.long_input_multiplier
    nano += (
        profile.max_output_tokens * card.output_nano_usd * card.long_output_multiplier_milli + 999
    ) // 1000
    return _micro(nano, batch)


def actual_cost(usage: TeacherUsage, card: TeacherPriceCard, *, batch=False) -> int:
    usage = TeacherUsage.model_validate(usage.model_dump())
    long = (
        card.long_context_threshold is not None and usage.input_tokens > card.long_context_threshold
    )
    input_multiplier = card.long_input_multiplier if long else 1
    output_multiplier = card.long_output_multiplier_milli if long else 1000
    nano = (
        (usage.input_tokens - usage.cached_input_tokens) * card.input_nano_usd
        + usage.cached_input_tokens * card.cached_input_nano_usd
    ) * input_multiplier
    nano += (usage.output_tokens * card.output_nano_usd * output_multiplier + 999) // 1000
    return _micro(nano, batch)
