"""
transaction_set.py

Defines the Eligibility 270 005010X279A1 transaction set model.
"""

from typing import Dict, List, Tuple

from pydantic import model_validator

from x12sdk.access import EligibilityAccess
from x12sdk.models import X12SegmentGroup
from x12sdk.validators import validate_segment_count

from .loops import Footer, Header, Loop2000A


class EligibilityInquiry(EligibilityAccess, X12SegmentGroup):
    """
    The ASC X12 270 (EligibilityInquiry) transaction model.
    """

    header: Header
    loop_2000a: List[Loop2000A]
    footer: Footer

    _validate_segment_count = model_validator(mode="after")(validate_segment_count)

    @model_validator(mode="after")
    def validate_subscriber_name(self):
        """
        Validates that the subscriber mame is present if the subscriber is a patient

        :param values: The raw, unvalidated transaction data.
        """
        values = self.__dict__
        for info_source in values.get("loop_2000a", []):
            for info_receiver in info_source.loop_2000b:
                for subscriber in info_receiver.loop_2000c:
                    child_code = subscriber.hl_segment.hierarchical_child_code
                    first_name = subscriber.loop_2100c.nm1_segment.name_first

                    if child_code == "0" and not first_name:
                        raise ValueError(
                            "name_first is required when the subscriber is the patient"
                        )

        return self

    @model_validator(mode="after")
    def validate_subscriber_hierarchy_child_code(self):
        """
        Validates that a subscriber's hierarchy child code is set correctly based on the presence of a dependent loop.

        :param values: The raw, unvalidated transaction data.
        """
        values = self.__dict__
        for info_source in values.get("loop_2000a", []):
            for info_receiver in info_source.loop_2000b:
                for subscriber in info_receiver.loop_2000c:
                    child_code = subscriber.hl_segment.hierarchical_child_code

                    if child_code == "1" and not subscriber.loop_2000d:
                        raise ValueError(
                            f"Invalid subscriber hierarchy code {child_code} no dependent record is present"
                        )
        return self

    @model_validator(mode="after")
    def validate_hierarchy_ids(self):
        """
        Validates the HL segments linkage in regards to the entire EligibilityInquiry transaction.
        Validations are limited to checks that are not covered within a segment or field scope.

        :param values: The raw, unvalidated transaction data.

        Each HL names its own parent, so that is what is checked. An earlier
        version also required every HL to be parented by the *previous* HL in
        the file, which is not an X12 rule: it made more than one subscriber
        per information receiver impossible to express, because the second
        subscriber would have had to be parented by the first. A provider
        checking eligibility for a list of patients is the ordinary use of a
        270, and no sample in the corpus has more than one subscriber, so the
        contradiction never fired.
        """
        values = self.__dict__

        def get_ids(hl_segment: Dict) -> Tuple[int, int]:
            """returns tuple of (id, parent_id)"""
            id = hl_segment.hierarchical_id_number
            parent_id = hl_segment.hierarchical_parent_id_number
            return int(id) if id else 0, int(parent_id) if parent_id else 0

        for info_source in values.get("loop_2000a", []):
            # info source does not have a parent id, since it starts a new hierarchy - this is validated at the
            # segment level
            source_id, _ = get_ids(info_source.hl_segment)
            for info_receiver in info_source.loop_2000b:
                receiver_id, receiver_parent_id = get_ids(info_receiver.hl_segment)

                if receiver_parent_id != source_id:
                    raise ValueError(
                        f"receiver parent id {receiver_parent_id} != source id {source_id}"
                    )

                for subscriber in info_receiver.loop_2000c:
                    subscriber_id, subscriber_parent_id = get_ids(subscriber.hl_segment)

                    if subscriber_parent_id != receiver_id:
                        raise ValueError(
                            f"subscriber parent id {subscriber_parent_id} != receiver id {receiver_id}"
                        )

                    if not subscriber.loop_2000d:
                        continue

                    for dependent in subscriber.loop_2000d:
                        dependent_id, dependent_parent_id = get_ids(
                            dependent.hl_segment
                        )

                        if dependent_parent_id != subscriber_id:
                            raise ValueError(
                                f"dependent parent id {dependent_parent_id} != subscriber id {subscriber_id}"
                            )

        return self
