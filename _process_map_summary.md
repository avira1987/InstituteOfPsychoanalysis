## Therapy lifecycle (SOP 2-17)

### start_therapy (SOP None)
- Name (fa): آغاز درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/start_therapy.json
- registry: processes/start_therapy
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- Workflow:
  1. eligibility_check --(duplicate_attempt)--> already_completed [system] [already_started_therapy]
  2. eligibility_check --(eligible)--> therapist_selection [system] [student_eligible_for_therapy, therapy_not_started]
  3. eligibility_check --(not_eligible)--> ineligible [system] [student_not_eligible]
  4. eligibility_check --(week9_deadline_exceeded)--> week9_blocked [system] [week_9_deadline]
  5. therapist_selection --(therapist_selected)--> therapist_confirmation [student]
  6. therapist_confirmation --(therapist_accepted)--> schedule_first_session [therapist]
  7. therapist_confirmation --(therapist_declined)--> therapist_selection [therapist]
  8. schedule_first_session --(session_time_selected)--> first_session_24h_check [student] [schedule_valid_for_course]
  9. first_session_24h_check --(24h_check_passed)--> payment_pending [system] [24_hour_rule]
  10. payment_pending --(payment_failed)--> payment_pending [system]
  ... +1 transitions

### therapy_changes (SOP 3)
- Name (fa): درت تغرات درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_changes.json
- registry: processes/therapy_changes
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- Workflow:
  1. change_request --(request_submitted)--> restart_review [student] [change_type_is_restart]
  2. change_request --(request_submitted)--> therapist_change_review [student] [change_type_is_therapist]
  3. change_request --(request_submitted)--> schedule_change_review [student] [change_type_is_schedule]
  4. restart_review --(restart_approved)--> restart_activated [progress_committee]
  5. restart_review --(restart_rejected)--> change_rejected [progress_committee]
  6. therapist_change_review --(therapist_change_approved)--> new_therapist_selection [progress_committee]
  7. therapist_change_review --(therapist_change_rejected)--> change_rejected [progress_committee]
  8. new_therapist_selection --(new_therapist_confirmed)--> change_approved [student]
  9. schedule_change_review --(schedule_change_approved)--> new_schedule_confirmation [therapist]
  10. schedule_change_review --(schedule_change_rejected)--> change_rejected [therapist]
  ... +1 transitions

### extra_session (SOP 4)
- Name (fa): برگزار جس اضاف درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/extra_session.json
- registry: processes/extra_session
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- INDEX sub_process_refs: attendance_tracking
- Workflow:
  1. extra_request --(extra_requested)--> therapist_review [student]
  2. therapist_review --(therapist_approved)--> payment_required [therapist]
  3. therapist_review --(therapist_proposed_alternative)--> student_response [therapist]
  4. therapist_review --(therapist_unavailable)--> extra_request_rejected [therapist]
  5. student_response --(student_confirmed_alternative)--> payment_required [student]
  6. student_response --(student_reentered_time)--> extra_request [student]
  7. payment_required --(payment_completed)--> extra_session_confirmed [system]
  8. payment_required --(payment_failed)--> payment_required [system]
  9. payment_required --(payment_timeout)--> extra_session_cancelled [system]
  10. extra_session_confirmed --(session_held)--> extra_session_completed [therapist]
  ... +1 transitions

### session_payment (SOP 5)
- Name (fa): پرداخت برا جسات آت درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/session_payment.json
- registry: processes/session_payment
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, system
- Workflow:
  1. payment_due --(student_initiated_payment)--> payment_selection [student]
  2. payment_selection --(payment_selection_submitted)--> awaiting_payment [student] [payment_selection_valid]
  3. payment_selection --(selection_invalid)--> payment_due [system]
  4. awaiting_payment --(payment_successful)--> payment_confirmed [system]
  5. awaiting_payment --(payment_unsuccessful)--> payment_failed [system]
  6. payment_failed --(retry_payment)--> awaiting_payment [student]
  7. payment_failed --(max_retries_exceeded)--> session_suspended [system] [payment_max_retries_exceeded]
  8. awaiting_payment --(payment_timeout)--> payment_failed [system]

### attendance_tracking (SOP 6)
- Name (fa): تک شد ساعات درا آزش (حضر  غاب)
- Status: complete_in_metadata
- metadata: metadata/processes/attendance_tracking.json
- registry: processes/attendance_tracking
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: therapist, site_manager, deputy_education, system
- INDEX sub_process_refs: fee_determination
- Runtime chains: fee_determination
- Workflow:
  1. session_scheduled --(session_time_reached)--> recording_closed [system] [student_on_leave]
  2. session_scheduled --(session_time_reached)--> recording_closed [system] [session_cancelled]
  3. session_scheduled --(session_time_reached)--> auto_absence_unpaid [system] [session_not_paid]
  4. session_scheduled --(session_time_reached)--> therapist_recording [system] [session_paid, student_not_on_leave, session_not_cancelled]
  5. therapist_recording --(student_present)--> session_completed [therapist]
  6. therapist_recording --(student_absent)--> absence_recorded [therapist]
  7. therapist_recording --(therapist_did_not_record)--> site_manager_pending [system]
  8. site_manager_pending --(site_manager_followed_up)--> therapist_recording [site_manager]
  9. site_manager_pending --(site_manager_sla_breach)--> deputy_escalated [system]
  10. absence_recorded --(absence_excused)--> excused_absence [system] [absence_is_excused]
  ... +2 transitions

### fee_determination (SOP 7)
- Name (fa): تع تکف ز جس درا آزش ا سپر فرد
- Status: complete_in_metadata
- metadata: metadata/processes/fee_determination.json
- registry: processes/fee_determination
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- Workflow:
  1. triggered --(precheck)--> excluded [system] [student_on_leave]
  2. triggered --(precheck)--> excluded [system] [session_cancelled_by_provider]
  3. triggered --(evaluate)--> scenario_1_credit_returned [system] [session_paid, absence_quota_not_exceeded]
  4. triggered --(evaluate)--> scenario_2_no_action [system] [session_not_paid, absence_quota_not_exceeded]
  5. triggered --(evaluate)--> scenario_3_forfeited [system] [session_paid, absence_quota_exceeded]
  6. triggered --(evaluate)--> scenario_4_debt_created [system] [session_not_paid, absence_quota_exceeded]

### therapy_completion (SOP 8)
- Name (fa): تک  خات درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_completion.json
- registry: processes/therapy_completion
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- Workflow:
  1. initiated --(process_link_clicked)--> conditions_not_met [student] [completion_conditions_not_met]
  2. initiated --(process_link_clicked)--> therapy_completed [student] [therapy_threshold_met, clinical_threshold_met, supervision_threshold_met]

### therapy_session_increase (SOP 9)
- Name (fa): درخاست داشج برا افزاش جسات فتگ درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_session_increase.json
- registry: processes/therapy_session_increase
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, therapist, system
- Workflow:
  1. request_submitted --(day_time_entered)--> therapist_review [student] [comprehensive_course_only]
  2. therapist_review --(therapist_approved)--> session_added [therapist]
  3. therapist_review --(therapist_proposed_alternative)--> student_response [therapist]
  4. therapist_review --(therapist_rejected)--> request_rejected [therapist]
  5. student_response --(student_confirmed_proposal)--> session_added [student]
  6. student_response --(student_reentered_time)--> therapist_review [student]

### therapy_session_reduction (SOP 10)
- Name (fa): درخاست داشج برا کاش جسات فتگ درا آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_session_reduction.json
- registry: processes/therapy_session_reduction
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, system, monitoring_committee_officer
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. initiated --(process_link_clicked)--> blocked [student] [fewer_than_2_weekly_sessions]
  2. initiated --(process_link_clicked)--> session_selection [student] [has_2_or_more_weekly_sessions]
  3. session_selection --(sessions_selected)--> reduction_completed [student] [reduction_results_in_2_plus]
  4. session_selection --(sessions_selected)--> reduction_completed [student] [reduction_results_in_1, therapy_threshold_met, clinical_threshold_met, supervision_threshold_met]
  5. session_selection --(sessions_selected)--> violation_warning [student] [reduction_results_in_1, completion_conditions_not_met]
  6. violation_warning --(student_confirmed_with_violation)--> reduction_with_violation [student]

### therapy_early_termination (SOP 11)
- Name (fa): طع زدرس درا آزش تسط دراگر آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_early_termination.json
- registry: processes/therapy_early_termination
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: therapist, student, system, monitoring_committee_officer
- INDEX sub_process_refs: violation_registration, specialized_commission_review, committees_review
- Runtime chains: violation_registration
- Workflow:
  1. reason_selection --(reason_submitted)--> awaiting_student_restart [therapist] [termination_reason_1_or_2]
  2. awaiting_student_restart --(student_restarted_therapy)--> restart_completed [student]
  3. awaiting_student_restart --(sla_5days_breach)--> violation_no_restart [system]
  4. reason_selection --(reason_submitted)--> scientific_referred [therapist] [termination_reason_3]
  5. reason_selection --(reason_submitted)--> disciplinary_referred [therapist] [termination_reason_4]

### specialized_commission_review (SOP 12)
- Name (fa): بررس کس تخصص (زرفراد اف)
- Status: complete_in_metadata
- metadata: metadata/processes/specialized_commission_review.json
- registry: processes/specialized_commission_review
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt
- Roles: specialized_commission, student, system, monitoring_committee_officer
- INDEX sub_process_refs: violation_registration, committees_review
- Runtime chains: committees_review, violation_registration
- Workflow:
  1. commission_review --(commission_approved)--> awaiting_student_restart [specialized_commission]
  2. commission_review --(commission_rejected)--> referred_to_committees [specialized_commission]
  3. awaiting_student_restart --(student_restarted_therapy)--> restart_completed [student]
  4. awaiting_student_restart --(sla_5days_breach)--> violation_no_restart [system]

### committees_review (SOP 13)
- Name (fa): بررس کتا ظارت  آزش (زرفراد ب)
- Status: complete_in_metadata
- metadata: metadata/processes/committees_review.json
- registry: processes/committees_review
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: supervision_committee, education_committee, student, system, deputy_education, monitoring_committee_officer
- INDEX sub_process_refs: violation_registration, patient_referral
- Runtime chains: patient_referral, violation_registration
- Workflow:
  1. supervision_review --(supervision_recommendation_submitted)--> education_review [supervision_committee]
  2. supervision_review --(supervision_sla_breach)--> supervision_review [system]
  3. education_review --(education_verdict_continue)--> awaiting_student_restart [education_committee]
  4. education_review --(education_verdict_terminate)--> education_terminated [education_committee]
  5. education_review --(education_sla_breach)--> education_review [system]
  6. awaiting_student_restart --(student_restarted_therapy)--> restart_completed [student]
  7. awaiting_student_restart --(sla_5days_breach)--> violation_no_restart [system]

### therapist_session_cancellation (SOP 14)
- Name (fa): کس کرد جس از س دراگر آزش
- Status: complete_in_metadata
- metadata: metadata/processes/therapist_session_cancellation.json
- registry: processes/therapist_session_cancellation
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: therapist, student, system
- INDEX sub_process_refs: attendance_tracking
- Workflow:
  1. session_selection --(session_selected)--> make_up_choice [therapist]
  2. make_up_choice --(no_make_up)--> cancelled_no_make_up [therapist]
  3. make_up_choice --(make_up_date_entered)--> make_up_proposed [therapist]
  4. make_up_proposed --(student_confirmed)--> make_up_confirmed [student] [has_credit_sessions]
  5. make_up_proposed --(student_confirmed)--> payment_required [student] [no_credit_sessions]
  6. payment_required --(payment_completed)--> make_up_confirmed [system]
  7. make_up_proposed --(student_rejected_and_proposed)--> therapist_review_alternative [student]
  8. therapist_review_alternative --(therapist_entered_new_makeup)--> make_up_proposed [therapist]
  9. therapist_review_alternative --(therapist_declined_makeup)--> cancelled_no_make_up [therapist]
  10. make_up_proposed --(student_declined_makeup)--> cancelled_student_declined [student]

### unannounced_absence_reaction (SOP 15)
- Name (fa): اکش استت ب غبت بد اطاع در جس آد
- Status: complete_in_metadata
- metadata: metadata/processes/unannounced_absence_reaction.json
- registry: processes/unannounced_absence_reaction
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: site_manager, therapy_committee_chair, therapy_committee_executor, system
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. identified --(system_check)--> stopped_on_leave [system] [student_on_leave]
  2. identified --(system_check)--> first_absence_handled [system] [first_unannounced_absence]
  3. identified --(system_check)--> site_manager_review [system] [two_consecutive_unannounced]
  4. site_manager_review --(site_manager_option_1)--> option_1_violation [site_manager]
  5. site_manager_review --(site_manager_option_2)--> committee_pending [site_manager]
  6. site_manager_review --(site_manager_option_3)--> ambiguous_3week_wait [site_manager]
  7. ambiguous_3week_wait --(student_started_therapy_changes)--> student_returned [system]
  8. ambiguous_3week_wait --(sla_3weeks_breach)--> committee_pending [system]
  9. committee_pending --(chair_delegated)--> committee_executor_review [therapy_committee_chair]
  10. committee_executor_review --(executor_option_a)--> violation_reported [therapy_committee_executor]
  ... +1 transitions

### therapy_interruption (SOP 16)
- Name (fa): ف در درا آزش تسط داشج
- Status: complete_in_metadata
- metadata: metadata/processes/therapy_interruption.json
- registry: processes/therapy_interruption
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, progress_committee, system
- INDEX sub_process_refs: violation_registration, patient_referral
- Runtime chains: patient_referral, violation_registration
- Workflow:
  1. request_submitted --(dates_entered)--> committee_scheduling [student]
  2. committee_scheduling --(meeting_scheduled)--> meeting_held [progress_committee]
  3. meeting_held --(committee_rejected)--> rejected [progress_committee]
  4. meeting_held --(committee_approved)--> awaiting_return [progress_committee] [interruption_less_than_42_days]
  5. meeting_held --(committee_approved)--> long_interruption_applied [progress_committee] [interruption_42_days_or_more]
  6. awaiting_return --(student_resumed_therapy)--> returned_successfully [system]
  7. awaiting_return --(student_did_not_return)--> no_return_resources_freed [system]

### student_session_cancellation (SOP 17)
- Name (fa): کس کرد جسات درا آزش تسط داشج
- Status: complete_in_metadata
- metadata: metadata/processes/student_session_cancellation.json
- registry: processes/student_session_cancellation
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, system
- INDEX sub_process_refs: violation_registration, fee_determination
- Runtime chains: fee_determination, violation_registration
- Workflow:
  1. calendar_displayed --(student_selects_sessions)--> consecutive_blocked [student] [would_exceed_3_consecutive_weeks]
  2. calendar_displayed --(student_selects_sessions)--> sessions_selected [student] [consecutive_weeks_valid]
  3. sessions_selected --(student_confirms)--> cancellation_applied [student] [cancellation_below_10_percent]
  4. sessions_selected --(student_confirms)--> warning_and_applied [student] [cancellation_10_to_12_percent]
  5. sessions_selected --(student_confirms)--> violation_and_applied [student] [cancellation_above_12_percent]

## Supervision lifecycle (SOP 18-28)

### supervision_block_transition (SOP 18)
- Name (fa): درت تغرات سپر فرد (آغاز جدد تغر سپرازر تغر ساعت)
- Status: complete_in_metadata
- metadata: metadata/processes/supervision_block_transition.json
- registry: processes/supervision_block_transition
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, system
- INDEX sub_process_refs: session_payment
- Runtime chains: session_payment
- Workflow:
  1. payment_intent_50th --(check_attendance)--> not_at_50th [student] [not_at_50th_supervision_session]
  2. payment_intent_50th --(check_attendance)--> supervisor_slots_displayed [student] [at_50th_supervision_session]
  3. supervisor_slots_displayed --(student_selects_supervisor_and_time)--> slot_selected [student] [max_one_session_per_week]
  4. slot_selected --(payment_success_new_block_first)--> new_block_first_paid [student]
  5. new_block_first_paid --(payment_success_50th)--> both_paid_completed [student]

### supervision_50h_completion (SOP 20)
- Name (fa): تک درا ۵۰ ساعت سپر فرد
- Status: complete_in_metadata
- metadata: metadata/processes/supervision_50h_completion.json
- registry: processes/supervision_50h_completion
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervisor, site_manager, system
- INDEX sub_process_refs: fee_determination, violation_registration
- Runtime chains: fee_determination, violation_registration
- Workflow:
  1. session_scheduled --(session_time_reached)--> recording_closed [system] [session_cancelled]
  2. session_scheduled --(session_time_reached)--> recording_closed [system] [student_on_supervision_leave]
  3. session_scheduled --(session_time_reached)--> auto_absence_unpaid [system] [supervision_session_not_paid]
  4. session_scheduled --(session_time_reached)--> supervisor_recording [system] [supervision_session_paid, student_not_on_supervision_leave, session_not_cancelled]
  5. supervisor_recording --(student_present)--> session_completed [supervisor] [at_49th_supervision_session]
  6. supervisor_recording --(student_present)--> evaluation_pending [supervisor] [at_49th_supervision_session]
  7. supervisor_recording --(student_present)--> session_completed [supervisor] [not_at_48_or_49_supervision_session]
  8. supervisor_recording --(student_absent)--> absence_recorded [supervisor]
  9. absence_recorded --(absence_fee_started)--> session_completed [system]
  10. supervisor_recording --(supervisor_did_not_record)--> site_manager_pending [system]
  ... +4 transitions

### supervision_session_increase (SOP 21)
- Name (fa): درخاست داشج برا افزاش جسات فتگ سپر
- Status: complete_in_metadata
- metadata: metadata/processes/supervision_session_increase.json
- registry: processes/supervision_session_increase
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervisor, system
- INDEX sub_process_refs: supervision_50h_completion
- Workflow:
  1. request_submitted --(day_time_entered)--> supervisor_review [student] [comprehensive_course_only]
  2. supervisor_review --(supervisor_approved)--> session_added [supervisor]
  3. supervisor_review --(supervisor_proposed_alternative)--> student_response [supervisor]
  4. supervisor_review --(supervisor_rejected)--> request_rejected [supervisor]
  5. student_response --(student_confirmed_proposal)--> session_added [student]
  6. student_response --(student_reentered_time)--> supervisor_review [student]

### extra_supervision_session (SOP 22)
- Name (fa): درخاست داشج برا برگزار جس اضاف سپر
- Status: complete_in_metadata
- metadata: metadata/processes/extra_supervision_session.json
- registry: processes/extra_supervision_session
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervisor, system
- INDEX sub_process_refs: session_payment, supervision_50h_completion
- Workflow:
  1. extra_request --(extra_requested)--> supervisor_review [student]
  2. supervisor_review --(supervisor_approved)--> payment_required [supervisor]
  3. supervisor_review --(supervisor_proposed_alternative)--> student_response [supervisor]
  4. supervisor_review --(supervisor_unavailable)--> extra_request_rejected [supervisor]
  5. student_response --(student_confirmed_alternative)--> payment_required [student]
  6. student_response --(student_reentered_time)--> supervisor_review [student]
  7. payment_required --(payment_completed)--> extra_session_confirmed [student]
  8. payment_required --(payment_failed)--> payment_required [system]
  9. extra_session_confirmed --(session_held)--> extra_session_completed [supervisor]

### supervision_session_reduction (SOP 24)
- Name (fa): درخاست داشج برا کاش جسات فتگ سپر
- Status: complete_in_metadata
- metadata: metadata/processes/supervision_session_reduction.json
- registry: processes/supervision_session_reduction
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervisor, system
- Workflow:
  1. initiated --(process_link_clicked)--> session_selection [student] [has_2_or_more_weekly_supervision_sessions]
  2. session_selection --(sessions_selected)--> multi_reduction_completed [student] [supervision_reduction_leaves_at_least_1]
  3. initiated --(process_link_clicked)--> eligibility_blocked [student] [fewer_than_2_weekly_supervision_sessions, completion_conditions_not_met]
  4. initiated --(process_link_clicked)--> structure_selection [student] [fewer_than_2_weekly_supervision_sessions, therapy_threshold_met, clinical_threshold_met, supervision_threshold_met]
  5. structure_selection --(frequency_day_time_entered)--> supervisor_review [student]
  6. supervisor_review --(supervisor_approved)--> frequency_reduction_completed [supervisor]
  7. supervisor_review --(supervisor_rejected)--> structure_selection [supervisor]

### student_supervision_cancellation (SOP 25)
- Name (fa): کس کرد جسات سپر تسط داشج  اکش استت
- Status: complete_in_metadata
- metadata: metadata/processes/student_supervision_cancellation.json
- registry: processes/student_supervision_cancellation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervisor, system
- INDEX sub_process_refs: violation_registration, fee_determination
- Runtime chains: fee_determination, violation_registration
- Workflow:
  1. calendar_displayed --(student_selects_sessions)--> consecutive_blocked [student] [would_exceed_3_consecutive_weeks]
  2. calendar_displayed --(student_selects_sessions)--> sessions_selected [student] [consecutive_weeks_valid]
  3. sessions_selected --(student_confirms)--> cancellation_applied [student] [cancellation_below_10_percent]
  4. sessions_selected --(student_confirms)--> warning_and_applied [student] [cancellation_10_to_12_percent]
  5. sessions_selected --(student_confirms)--> violation_and_applied [student] [cancellation_above_12_percent]

### supervisor_session_cancellation (SOP 26)
- Name (fa): کس کرد جس از س سپرازر
- Status: complete_in_metadata
- metadata: metadata/processes/supervisor_session_cancellation.json
- registry: processes/supervisor_session_cancellation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: supervisor, student, system
- INDEX sub_process_refs: supervision_50h_completion
- Workflow:
  1. session_selection --(session_selected)--> makeup_choice [supervisor]
  2. makeup_choice --(no_makeup_selected)--> cancelled_no_makeup [supervisor]
  3. makeup_choice --(makeup_date_entered)--> makeup_proposed [supervisor]
  4. makeup_proposed --(student_confirmed)--> makeup_confirmed [student] [supervision_session_paid]
  5. makeup_proposed --(student_confirmed)--> payment_pending [student] [supervision_session_not_paid]
  6. payment_pending --(payment_completed)--> makeup_confirmed [system]
  7. makeup_proposed --(student_counter_proposed)--> supervisor_review_counter [student]
  8. supervisor_review_counter --(supervisor_entered_new_time)--> makeup_proposed [supervisor]
  9. makeup_proposed --(student_declined_makeup)--> student_declined_makeup [student]
  10. makeup_confirmed --(session_held)--> makeup_session_completed [supervisor]

### unannounced_supervision_absence_reaction (SOP 27)
- Name (fa): اکش استت ب غبت بد اطاع در جس آد سپر فرد
- Status: complete_in_metadata
- metadata: metadata/processes/unannounced_supervision_absence_reaction.json
- registry: processes/unannounced_supervision_absence_reaction
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: site_manager, therapy_committee_chair, therapy_committee_executor, deputy_education, system
- INDEX sub_process_refs: fee_determination, violation_registration, patient_referral
- Runtime chains: patient_referral, violation_registration
- Workflow:
  1. identified --(system_check)--> stopped_on_leave [system] [student_on_supervision_leave]
  2. identified --(system_check)--> first_absence_handled [system] [first_unannounced_absence]
  3. identified --(system_check)--> site_manager_review [system] [two_consecutive_unannounced]
  4. site_manager_review --(site_manager_option_1)--> option_1_violation [site_manager]
  5. site_manager_review --(site_manager_option_2)--> committee_pending [site_manager]
  6. site_manager_review --(site_manager_option_3)--> ambiguous_3week_wait [site_manager]
  7. ambiguous_3week_wait --(student_started_supervision_block_transition)--> student_returned [system]
  8. ambiguous_3week_wait --(sla_3weeks_breach)--> committee_pending [system]
  9. committee_pending --(chair_delegated)--> committee_executor_review [therapy_committee_chair]
  10. committee_executor_review --(executor_option_a)--> violation_reported [therapy_committee_executor]
  ... +1 transitions

### supervision_interruption (SOP 28)
- Name (fa): ف در سپر فرد تسط داشج
- Status: complete_in_metadata
- metadata: metadata/processes/supervision_interruption.json
- registry: processes/supervision_interruption
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, progress_committee, system
- INDEX sub_process_refs: violation_registration, patient_referral
- Runtime chains: patient_referral, violation_registration
- Workflow:
  1. request_submitted --(pause_dates_entered)--> committee_scheduling [student]
  2. committee_scheduling --(meeting_scheduled)--> meeting_held [progress_committee]
  3. meeting_held --(committee_rejected)--> rejected [progress_committee]
  4. meeting_held --(committee_approved)--> approved_short_pause [progress_committee] [pause_less_than_21_days]
  5. meeting_held --(committee_approved)--> approved_long_pause [progress_committee] [pause_21_days_or_more]
  6. approved_short_pause --(pause_end_date_reached)--> monitoring_return [system]
  7. monitoring_return --(student_attended_first_session)--> returned_successfully [system]
  8. monitoring_return --(student_absent_first_session)--> absent_resources_released [system]

## Academic calendar and enrollment (SOP 29-42)

### fall_semester_preparation (SOP 29)
- Name (fa): آادساز تر پاز
- Status: complete_in_metadata
- metadata: metadata/processes/fall_semester_preparation.json
- registry: processes/fall_semester_preparation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: course_committee_executive, deputy_education, course_committee_scientific, admissions_officer, site_manager, system
- Workflow:
  1. calendar_entry --(calendar_submitted)--> tuition_entry [course_committee_executive]
  2. calendar_entry --(sla_expired)--> calendar_entry [system]
  3. tuition_entry --(tuition_submitted)--> license_check [deputy_education_director]
  4. tuition_entry --(sla_expired)--> tuition_entry [system]
  5. license_check --(license_reviewed)--> course_list_creation [deputy_education_director]
  6. license_check --(sla_expired)--> license_check [system]
  7. course_list_creation --(course_list_submitted)--> course_finalization [scientific_officer_course_committee]
  8. course_list_creation --(sla_expired)--> course_list_creation [system]
  9. course_finalization --(courses_finalized)--> marketing_campaign [scientific_officer_course_committee]
  10. course_finalization --(sla_expired)--> course_finalization [system]
  ... +6 transitions

### winter_semester_preparation (SOP 30)
- Name (fa): آادساز تر زستا
- Status: complete_in_metadata
- metadata: metadata/processes/winter_semester_preparation.json
- registry: processes/winter_semester_preparation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: deputy_education, course_committee_scientific, admissions_officer, site_manager, system
- INDEX sub_process_refs: fall_semester_preparation
- Workflow:
  1. license_check --(license_reviewed)--> course_list_review [deputy_education_director]
  2. license_check --(sla_expired)--> license_check [system]
  3. course_list_review --(course_list_reviewed)--> course_finalization [scientific_officer_course_committee]
  4. course_list_review --(sla_expired)--> course_list_review [system]
  5. course_finalization --(courses_finalized)--> marketing_campaign [scientific_officer_course_committee]
  6. course_finalization --(sla_expired)--> course_finalization [system]
  7. marketing_campaign --(marketing_started)--> interviewer_assignment [admissions_officer]
  8. marketing_campaign --(sla_expired)--> marketing_campaign [system]
  9. interviewer_assignment --(interviewers_assigned)--> interview_scheduling [deputy_education_director]
  10. interviewer_assignment --(sla_expired)--> interviewer_assignment [system]
  ... +2 transitions

### introductory_course_registration (SOP 31)
- Name (fa): فرایند ثبت‌نام دوره آشنایی
- Status: complete_in_metadata
- metadata: metadata/processes/introductory_course_registration.json
- registry: processes/introductory_course_registration
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: applicant, admissions_officer, interviewer, system
- Workflow:
  1. application_submitted --(timeslot_selected)--> interview_payment [applicant]
  2. interview_scheduled --(proceed_to_payment)--> interview_payment [applicant]
  3. interview_payment --(payment_success)--> interview_payment_confirmed [system]
  4. interview_payment --(payment_failed)--> interview_payment [system]
  5. interview_payment_confirmed --(interview_time_reached)--> interview_completed [system]
  6. interview_completed --(interview_result_submitted)--> result_conditional_therapy [interviewer] [result == 'conditional_therapy']
  7. interview_completed --(interview_result_submitted)--> result_single_course [interviewer] [result == 'single_course']
  8. interview_completed --(interview_result_submitted)--> result_full_admission [interviewer] [result == 'full_admission']
  9. interview_completed --(interview_result_submitted)--> rejected [interviewer] [result == 'rejected']
  10. result_conditional_therapy --(proceed_to_documents)--> documents_upload [system]
  ... +12 transitions

### introductory_term_end (SOP 32)
- Name (fa): پاا ترا در آشا
- Status: complete_in_metadata
- metadata: metadata/processes/introductory_term_end.json
- registry: processes/introductory_term_end
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: admissions_officer, deputy_education, system
- Workflow:
  1. grades_submitted --(auto_generate_transcripts)--> transcript_generated [system]
  2. transcript_generated --(transcripts_ready)--> therapy_check [system]
  3. therapy_check --(therapy_condition_check)--> therapy_blocked [system] [admission_type == 'conditional_therapy', no_active_therapist_registered]
  4. therapy_check --(therapy_condition_check)--> registration_notification_sent [system] [therapy_condition_met_or_not_conditional]
  5. therapy_blocked --(therapist_registered_later)--> registration_notification_sent [system] [active_therapist_registered]
  6. registration_notification_sent --(send_registration_notification)--> decline_list_generated [system]
  7. decline_list_generated --(decline_list_ready)--> followup_in_progress [system]
  8. followup_in_progress --(all_followups_done)--> followup_complete [admissions_officer]
  9. followup_in_progress --(sla_warning)--> followup_in_progress [system] [sla_approaching_168h]

### intro_second_semester_registration (SOP 33)
- Name (fa): ثبتا داشج برا تر د در آشا
- Status: complete_in_metadata
- metadata: metadata/processes/intro_second_semester_registration.json
- registry: processes/intro_second_semester_registration
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, system
- INDEX sub_process_refs: start_therapy
- Workflow:
  1. eligibility_check --(eligibility_check_result)--> therapy_check_failed [system] [admission_type == 'conditional_therapy', no_active_therapist_registered]
  2. eligibility_check --(eligibility_check_result)--> suspension_check_failed [system] [student_suspended]
  3. eligibility_check --(eligibility_check_result)--> course_selection [system] [eligible_for_registration]
  4. course_selection --(courses_confirmed)--> payment_method [student]
  5. payment_method --(payment_method_selected)--> payment_processing [student]
  6. payment_processing --(payment_completed)--> registration_complete [system] [term2_installment_payment]
  7. payment_processing --(payment_completed)--> term2_registration_closed [system] [term2_cash_payment]
  8. payment_processing --(payment_failed)--> payment_processing [system]
  9. registration_complete --(installment_due_date_passed)--> installment_overdue [system] [installment_not_paid]
  10. installment_overdue --(overdue_installment_paid)--> registration_complete [system]
  ... +1 transitions

### introductory_course_completion (SOP 34)
- Name (fa): خات در آشا
- Status: complete_in_metadata
- metadata: metadata/processes/introductory_course_completion.json
- registry: processes/introductory_course_completion
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: supervision_committee, system
- Workflow:
  1. all_courses_passed --(all_10_courses_passed)--> invitation_sent [system]
  2. invitation_sent --(generate_certificate_draft)--> certificate_draft_generated [system]
  3. certificate_draft_generated --(draft_ready_for_review)--> certificate_review [system]
  4. certificate_review --(committee_approved_certificate)--> certificate_approved [supervision_committee]
  5. certificate_review --(committee_requested_revision)--> certificate_draft_generated [supervision_committee]
  6. certificate_approved --(student_notified)--> process_complete [system]

### comprehensive_course_registration (SOP 35)
- Name (fa): ثبتا در در جاع
- Status: complete_in_metadata
- metadata: metadata/processes/comprehensive_course_registration.json
- registry: processes/comprehensive_course_registration
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, progress_committee_executive, progress_committee_scientific, admissions_officer, deputy_education, system
- Workflow:
  1. application_submitted --(application_submitted)--> supervision_committee_review [student] [all_10_introductory_courses_passed]
  2. supervision_committee_review --(supervision_approved)--> executive_review [supervision_committee]
  3. supervision_committee_review --(supervision_rejected)--> supervision_rejected [supervision_committee]
  4. supervision_committee_review --(supervision_sla_breach)--> supervision_committee_review [system]
  5. executive_review --(executive_opinion_submitted)--> scientific_review [progress_committee]
  6. executive_review --(executive_sla_breach)--> executive_review [system]
  7. scientific_review --(scientific_approved)--> document_upload [progress_committee]
  8. scientific_review --(scientific_rejected)--> scientific_rejected [progress_committee]
  9. scientific_review --(scientific_requested_proof)--> scientific_review [progress_committee]
  10. scientific_review --(scientific_sla_breach)--> scientific_review [system]
  ... +11 transitions

### comprehensive_term_end (SOP 36)
- Name (fa): پاا ترا در جاع
- Status: complete_in_metadata
- metadata: metadata/processes/comprehensive_term_end.json
- registry: processes/comprehensive_term_end
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: system
- Workflow:
  1. grades_submitted --(all_grades_entered)--> transcript_generated [system]
  2. transcript_generated --(transcripts_ready)--> graduation_check [system]
  3. graduation_check --(all_comprehensive_courses_passed)--> completed_all_courses [system] [all_comprehensive_subjects_passed]
  4. graduation_check --(remaining_courses_exist)--> registration_notification_sent [system] [has_remaining_comprehensive_courses]
  5. registration_notification_sent --(notification_delivered)--> process_complete [system]

### internship_readiness_consultation (SOP 37)
- Name (fa): شرت  تع آادگ برا آغاز اتر
- Status: complete_in_metadata
- metadata: metadata/processes/internship_readiness_consultation.json
- registry: processes/internship_readiness_consultation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, progress_committee, deputy_education, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. auto_trigger --(student_registered_request)--> student_request [student]
  2. student_request --(request_submitted)--> supervision_committee_review [student]
  3. supervision_committee_review --(supervision_rejected)--> supervision_rejected [supervision_committee]
  4. supervision_committee_review --(supervision_approved)--> interview_scheduling [supervision_committee]
  5. interview_scheduling --(interview_scheduled)--> interview_held [progress_committee_project]
  6. interview_held --(result_unconditional)--> interview_result_unconditional [progress_committee_scientific]
  7. interview_held --(result_conditional)--> interview_result_conditional [progress_committee_scientific]
  8. interview_held --(result_retry_30h)--> interview_result_retry [progress_committee_scientific]
  9. interview_result_unconditional --(proceed_to_contracts)--> contract_practice [system]
  10. interview_result_conditional --(proceed_to_contracts)--> contract_practice [system]
  ... +8 transitions

### internship_12month_conditional_review (SOP 38)
- Name (fa): ۱۲ ا پس از ب شرط در اتر
- Status: complete_in_metadata
- metadata: metadata/processes/internship_12month_conditional_review.json
- registry: processes/internship_12month_conditional_review
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, progress_committee, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. month_12_trigger --(alert_sent)--> supervision_review [system]
  2. supervision_review --(no_permit)--> supervision_rejected [supervision_committee]
  3. supervision_review --(permit_issued)--> interview_scheduling [supervision_committee]
  4. interview_scheduling --(interview_scheduled)--> interview_held [progress_committee_project]
  5. interview_held --(result_unrestricted)--> result_unrestricted [progress_committee_scientific]
  6. interview_held --(result_conditional)--> result_conditional [progress_committee_scientific]

### intern_hours_increase (SOP 39)
- Name (fa): اضاف شد حداکثر ساعتا ارائ درا اتر
- Status: complete_in_metadata
- metadata: metadata/processes/intern_hours_increase.json
- registry: processes/intern_hours_increase
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: supervision_committee, student, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. deadline_reached --(alert_to_supervision)--> supervision_review [system]
  2. supervision_review --(rejected)--> rejected_referral [supervision_committee]
  3. supervision_review --(approved)--> approved_time_coordination [supervision_committee]
  4. approved_time_coordination --(times_registered)--> hours_increased [supervision_committee]

### comprehensive_term_start (SOP 40)
- Name (fa): آغاز ترم‌های دوره جامع
- Status: complete_in_metadata
- metadata: metadata/processes/comprehensive_term_start.json
- registry: processes/comprehensive_term_start
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, course_committee_executive, system
- Workflow:
  1. eligibility_check --(suspended_or_on_leave)--> blocked [system]
  2. eligibility_check --(eligible)--> course_display [system]
  3. course_display --(courses_seen)--> payment_choice [student]
  4. payment_choice --(payment_initiated)--> payment_processing [student]
  5. payment_processing --(payment_confirmed)--> registration_complete [system]

### lesson_start_per_term (SOP 41)
- Name (fa): آغاز ر درس در ر تر
- Status: complete_in_metadata
- metadata: metadata/processes/lesson_start_per_term.json
- registry: processes/lesson_start_per_term
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_executive, system
- INDEX sub_process_refs: fall_semester_preparation, winter_semester_preparation
- Workflow:
  1. student_enrollment --(enrolled)--> links_created [student]
  2. links_created --(links_placed)--> attendance_list_ready [system]
  3. attendance_list_ready --(ready)--> lesson_active [system]

### student_non_registration (SOP 42)
- Name (fa): عد ثبتا داشج برا تر بعد
- Status: complete_in_metadata
- metadata: metadata/processes/student_non_registration.json
- registry: processes/student_non_registration
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, system
- INDEX sub_process_refs: violation_registration, educational_leave
- Workflow:
  1. list_generated --(meeting_scheduled)--> meeting_scheduled [supervision_committee]
  2. meeting_scheduled --(invitation_sent)--> meeting_held [system]
  3. meeting_held --(choice_register)--> branch_register [supervision_committee] [within_4_weeks_of_term_start]
  4. meeting_held --(choice_leave)--> branch_leave [supervision_committee]
  5. meeting_held --(choice_withdrawal)--> branch_withdrawal [supervision_committee]
  6. branch_register --(courses_selected)--> registration_completed [student]
  7. branch_register --(no_action_2_days)--> withdrawal_triggered [system]
  8. branch_leave --(leave_process_started)--> leave_started [student]
  9. branch_leave --(no_action_3_days)--> withdrawal_triggered [system]

## TA and instructor track (SOP 43-56)

### ta_conceptual_questions (SOP 43)
- Name (fa): ثبت ۳ سا تستف (ککدرس)
- Status: complete_in_metadata
- metadata: metadata/processes/ta_conceptual_questions.json
- registry: processes/ta_conceptual_questions
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, instructor, deputy_education, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. session_ended --(process_started)--> ta_upload [system]
  2. ta_upload --(upload_after_24h)--> upload_late [system]
  3. ta_upload --(uploaded_on_time)--> instructor_review [teaching_assistant]
  4. upload_late --(uploaded_late)--> instructor_review [teaching_assistant]
  5. instructor_review --(question_rejected)--> question_rejected [instructor]
  6. instructor_review --(all_accepted)--> questions_approved [instructor]
  7. question_rejected --(corrected_and_uploaded)--> instructor_review [teaching_assistant]

### ta_student_consultation (SOP 44)
- Name (fa): شاسا تش  شرت آزش (ککدرس)
- Status: complete_in_metadata
- metadata: metadata/processes/ta_student_consultation.json
- registry: processes/ta_student_consultation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, progress_committee, system
- Workflow:
  1. session_5_10_15 --(reminder_sent)--> ta_form_fill [system]
  2. ta_form_fill --(deadline_passed)--> form_locked [system]
  3. ta_form_fill --(form_submitted)--> form_submitted [teaching_assistant]

### ta_essay_upload (SOP 45)
- Name (fa): آپد جستار  دا تخب ف (ککدرس)
- Status: complete_in_metadata
- metadata: metadata/processes/ta_essay_upload.json
- registry: processes/ta_essay_upload
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, instructor, reference_center, marketing, deputy_education, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. session_ended --(process_started)--> ta_upload [system]
  2. ta_upload --(uploaded)--> instructor_review [teaching_assistant]
  3. instructor_review --(rejected)--> rejected_revision [instructor]
  4. instructor_review --(accepted)--> reference_center_editing [instructor]
  5. rejected_revision --(revised_and_uploaded)--> instructor_review [teaching_assistant]
  6. reference_center_editing --(sent_to_marketing)--> marketing_publication [reference_center]
  7. marketing_publication --(publication_recorded)--> content_published [marketing]

### ta_blog_content (SOP 46)
- Name (fa): ثبت حتا باگ از حتا درس (ککدرس)
- Status: complete_in_metadata
- metadata: metadata/processes/ta_blog_content.json
- registry: processes/ta_blog_content
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, instructor, marketing, deputy_education, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. session_ended --(process_started)--> ta_write [system]
  2. ta_write --(content_submitted)--> instructor_review [system]
  3. instructor_review --(rejected)--> rejected_revision [instructor]
  4. instructor_review --(accepted)--> approved_marketing_draft [instructor]
  5. rejected_revision --(revised_and_submitted)--> instructor_review [teaching_assistant]

### upgrade_to_ta (SOP 47)
- Name (fa): ارتا ب ککدرس
- Status: complete_in_metadata
- metadata: metadata/processes/upgrade_to_ta.json
- registry: processes/upgrade_to_ta
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, course_committee_scientific, course_committee_project, system
- Workflow:
  1. student_click --(conditions_failed)--> conditions_not_met [student]
  2. student_click --(conditions_met)--> supervision_review [student]
  3. supervision_review --(rejected)--> supervision_rejected [supervision_committee]
  4. supervision_review --(approved)--> interview_scheduling [supervision_committee]
  5. interview_scheduling --(interview_scheduled)--> interview_held [course_committee]
  6. interview_held --(rejected)--> course_committee_rejected [course_committee]
  7. interview_held --(approved)--> track_selection [course_committee]
  8. track_selection --(tracks_registered)--> commitment_signature [course_committee]
  9. commitment_signature --(commitment_signed)--> ta_registered [student]

### mentor_private_sessions (SOP 48)
- Name (fa): ثبت تارخ ۲ جس تدرس خصص درس ب ککدرس
- Status: complete_in_metadata
- metadata: metadata/processes/mentor_private_sessions.json
- registry: processes/mentor_private_sessions
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: instructor, teaching_assistant, course_committee_scientific, supervision_committee, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. instructor_click --(session_2_started_without_registration)--> deadline_missed [system]
  2. instructor_click --(sessions_entered)--> sessions_registered [instructor]
  3. sessions_registered --(registered)--> process_complete [system]

### ta_to_assistant_faculty (SOP 49)
- Name (fa): ارتا رتب از ککدرس ب دستار ئت ع
- Status: complete_in_metadata
- metadata: metadata/processes/ta_to_assistant_faculty.json
- registry: processes/ta_to_assistant_faculty
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, supervision_committee, course_committee_scientific, system
- Workflow:
  1. auto_or_manual_trigger --(already_has_rank)--> already_assistant [system]
  2. auto_or_manual_trigger --(request_sent)--> supervision_review [system]
  3. supervision_review --(rejected)--> supervision_rejected [supervision_committee]
  4. supervision_review --(approved)--> upgrade_applied [supervision_committee]

### ta_to_instructor_auto (SOP 50)
- Name (fa): تبد خدکار ککدرس ب درس در ر درس
- Status: complete_in_metadata
- metadata: metadata/processes/ta_to_instructor_auto.json
- registry: processes/ta_to_instructor_auto
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: system, course_committee_scientific, deputy_education
- Workflow:
  1. end_of_term_check --(conditions_failed)--> conditions_not_met [student]
  2. end_of_term_check --(conditions_met)--> upgrade_applied [student]

### ta_track_change (SOP 51)
- Name (fa): تغر ا اضاف کرد رست ککدرس
- Status: complete_in_metadata
- metadata: metadata/processes/ta_track_change.json
- registry: processes/ta_track_change
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, course_committee_scientific, system
- Workflow:
  1. ta_click --(path_chosen)--> path_selected [teaching_assistant]
  2. path_selected --(request_sent)--> course_committee_review [system]
  3. course_committee_review --(meeting_registered)--> meeting_scheduled [course_committee_scientific]
  4. meeting_scheduled --(rejected)--> rejected [course_committee_scientific]
  5. meeting_scheduled --(approved)--> track_applied [course_committee_scientific]

### ta_track_completion (SOP 52)
- Name (fa): خات ککدرس برا ر رست
- Status: complete_in_metadata
- metadata: metadata/processes/ta_track_completion.json
- registry: processes/ta_track_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: system, course_committee_scientific, teaching_assistant
- Workflow:
  1. end_of_track_check --(conditions_met)--> track_completed [student]

### ta_instructor_leave (SOP 53)
- Name (fa): رخص ککدرس  درس
- Status: complete_in_metadata
- metadata: metadata/processes/ta_instructor_leave.json
- registry: processes/ta_instructor_leave
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, instructor, course_committee_scientific, system
- Workflow:
  1. leave_request --(request_submitted)--> course_committee_review [teaching_assistant_or_instructor]
  2. course_committee_review --(rejected)--> leave_rejected [course_committee_scientific]
  3. course_committee_review --(substitute_chosen)--> substitute_assigned [course_committee_scientific]
  4. course_committee_review --(cancellation_chosen)--> classes_cancelled [course_committee_scientific]
  5. substitute_assigned --(substitute_confirmed)--> leave_approved [system]
  6. classes_cancelled --(cancellation_confirmed)--> leave_approved [system]

### class_attendance (SOP 54)
- Name (fa): حضر  غاب در تا کاسا
- Status: complete_in_metadata
- metadata: metadata/processes/class_attendance.json
- registry: processes/class_attendance
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: instructor, student, teaching_assistant, supervision_committee, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. attendance_list_ready --(attendance_submitted)--> session_recorded [instructor]
  2. session_recorded --(absence_count_5)--> incomplete_triggered [system] [attendance_absence_count_5]
  3. session_recorded --(absence_5_article_course)--> article_violation_reported [system] [attendance_absence_count_5, attendance_course_is_article_writing]

### violation_registration (SOP 55)
- Name (fa): ثبت تخفات
- Status: complete_in_metadata
- metadata: metadata/processes/violation_registration.json
- registry: processes/violation_registration
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, education_committee, deputy_education, system
- Workflow:
  1. violation_reported --(committee_reviewing)--> review_status_set [monitoring_committee_officer] [violation_reviewable_yes]
  2. violation_reported --(recorded_and_closed)--> closed [monitoring_committee_officer] [violation_reviewable_no]
  3. violation_reported --(first_action_sla_breach)--> violation_reported [system]
  4. review_status_set --(meeting_set)--> meeting_scheduled [supervision_committee] [violation_needs_meeting_yes]
  5. review_status_set --(verdict_direct)--> verdict_issued [supervision_committee] [violation_needs_meeting_no]
  6. review_status_set --(dismissed)--> closed [supervision_committee]
  7. meeting_scheduled --(verdict_issued)--> verdict_issued [supervision_committee]
  8. verdict_issued --(verdict_recorded)--> closed [supervision_committee] [violation_verdict_minor]
  9. verdict_issued --(suspension_next_term)--> suspension_next_term [supervision_committee] [violation_verdict_suspension_next_term]
  10. verdict_issued --(suspension_immediate)--> suspension_immediate [supervision_committee] [violation_verdict_suspension_immediate]
  ... +8 transitions

### class_session_cancellation (SOP 56)
- Name (fa): کس کرد جسات کاسا درس
- Status: complete_in_metadata
- metadata: metadata/processes/class_session_cancellation.json
- registry: processes/class_session_cancellation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: instructor, course_committee_scientific, student, teaching_assistant, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. cancellation_request --(cancellation_confirmed)--> makeup_scheduled [instructor]

### student_instructor_evaluation (SOP 57)
- Name (fa): ارزاب داشج از درس
- Status: complete_in_metadata
- metadata: metadata/processes/student_instructor_evaluation.json
- registry: processes/student_instructor_evaluation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, course_committee_scientific, system
- Workflow:
  1. evaluation_open --(deadline_reached)--> evaluation_closed [system]

## Leave and return (SOP 58-60)

### process_merged_to_one (SOP 58)
- Name (fa): تشد ب فراد شار ۱
- Status: complete_in_metadata
- metadata: metadata/processes/process_merged_to_one.json
- registry: processes/process_merged_to_one
- Registry artifacts: SOP_document.txt
- Roles: system
- INDEX sub_process_refs: educational_leave
- Workflow:
  1. merged --(noop)--> merged [system]

### full_education_leave (SOP 59)
- Name (fa): رخص ت از ک آزش
- Status: complete_in_metadata
- metadata: metadata/processes/full_education_leave.json
- registry: processes/full_education_leave
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, progress_committee, deputy_education, therapy_education_coordinator, monitoring_committee_officer, system
- INDEX sub_process_refs: return_to_full_education, patient_referral, violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. leave_request --(student_submitted)--> committee_review [student]
  2. committee_review --(sla_breach_7days)--> deputy_alerted [system]
  3. deputy_alerted --(committee_set_meeting)--> session_scheduled [progress_committee]
  4. committee_review --(committee_set_meeting)--> session_scheduled [progress_committee]
  5. session_scheduled --(meeting_held)--> committee_decision [progress_committee]
  6. committee_decision --(committee_rejected)--> leave_rejected [progress_committee]
  7. committee_decision --(committee_approved)--> therapist_assignment [progress_committee]
  8. therapist_assignment --(therapist_assigned)--> on_leave [therapy_education_coordinator]
  9. therapist_assignment --(skip_therapist_assignment)--> on_leave [system]
  10. therapist_assignment --(sla_breach_4days)--> on_leave [system]
  ... +4 transitions

### return_to_full_education (SOP 60)
- Name (fa): بازگشت دبار ب ک آزش پس از رخص از ک آزش
- Status: complete_in_metadata
- metadata: metadata/processes/return_to_full_education.json
- registry: processes/return_to_full_education
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, system
- INDEX sub_process_refs: full_education_leave
- Workflow:
  1. return_request --(proceed)--> therapist_selection [student]
  2. therapist_selection --(therapist_selected)--> therapy_24h_scheduled [student]
  3. therapy_24h_scheduled --(therapy_24h_passed)--> therapy_payment_pending [system]
  4. therapy_payment_pending --(payment_failed)--> therapy_payment_pending [system]
  5. therapy_payment_pending --(therapy_payment_confirmed)--> therapy_completed [system]
  6. therapy_completed --(needs_supervisor)--> supervisor_selection [system]
  7. therapy_completed --(skip_supervisor)--> registration_unlocked [system]
  8. supervisor_selection --(supervisor_selected)--> supervision_24h_scheduled [student]
  9. supervision_24h_scheduled --(supervision_24h_passed)--> supervision_payment_pending [system]
  10. supervision_payment_pending --(supervision_payment_confirmed)--> registration_unlocked [system]
  ... +1 transitions

### educational_leave (SOP None)
- Name (fa): رخص آزش ت از ثبتا در کاسا
- Status: complete_in_metadata
- metadata: metadata/processes/educational_leave.json
- registry: processes/educational_leave
- Registry artifacts: 01_input.md, 02_flowchart.md, 03_output.json, 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, progress_committee, deputy_education, monitoring_committee_officer
- INDEX sub_process_refs: violation_registration, patient_referral
- Runtime chains: patient_referral, violation_registration
- Workflow:
  1. request_form --(student_submitted)--> committee_review [student]
  2. committee_review --(sla_breach_7days)--> deputy_alerted [system]
  3. deputy_alerted --(committee_set_meeting)--> session_scheduled [progress_committee]
  4. committee_review --(committee_set_meeting)--> session_scheduled [progress_committee]
  5. session_scheduled --(meeting_held)--> committee_decision [progress_committee]
  6. committee_decision --(committee_rejected)--> rejected [progress_committee]
  7. committee_decision --(committee_approved)--> approved_non_intern [progress_committee] [is_not_intern]
  8. committee_decision --(committee_approved)--> approved_intern_1term [progress_committee] [is_intern, leave_terms_eq_1]
  9. committee_decision --(committee_approved)--> approved_intern_2term [progress_committee] [is_intern, leave_terms_eq_2]
  10. approved_non_intern --(leave_activated)--> on_leave [student]
  ... +5 transitions

## Course completion and graduation (SOP 61-75)

### theory_course_completion (SOP 61)
- Name (fa): خات درس تئر
- Status: complete_in_metadata
- metadata: metadata/processes/theory_course_completion.json
- registry: processes/theory_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. awaiting_session_18 --(calendar_session_18_reached)--> session_18_entry [system]
  2. session_18_entry --(session_18_submitted)--> final_exam_open [instructor] [theory_session_18_submitted_in_time]
  3. session_18_entry --(sla_breach)--> session_18_delay [system] [theory_session_18_sla_breach]
  4. final_exam_open --(exam_completed)--> borderline_student_choice [student] [theory_borderline_score]
  5. final_exam_open --(exam_completed)--> qualitative_eval_pending [student] [theory_not_borderline_score]
  6. final_exam_open --(exam_completed)--> borderline_student_choice [system] [theory_borderline_score]
  7. final_exam_open --(exam_completed)--> qualitative_eval_pending [system] [theory_not_borderline_score]
  8. borderline_student_choice --(repeat_course_selected)--> qualitative_eval_pending [student]
  9. borderline_student_choice --(retake_selected)--> retake_exam_open [student]
  10. retake_exam_open --(retake_exam_completed)--> qualitative_eval_pending [student]
  ... +3 transitions
- SOP step mappings (15 steps): see sop_step_mappings.json

### group_supervision_course_completion (SOP 62)
- Name (fa): خات ر درس سپر گر
- Status: complete_in_metadata
- metadata: metadata/processes/group_supervision_course_completion.json
- registry: processes/group_supervision_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. awaiting_session_18 --(calendar_session_18_reached)--> session_18_pass_fail_entry [system]
  2. session_18_pass_fail_entry --(pass_fail_submitted)--> pass_fail_applied [instructor] [group_supervision_pass_fail_in_time]
  3. session_18_pass_fail_entry --(sla_breach)--> session_18_delay [system] [group_supervision_pass_fail_sla_breach]
  4. pass_fail_applied --(hours_applied)--> ta_evaluation_entry [system] [group_supervision_has_ta]
  5. pass_fail_applied --(hours_applied)--> qualitative_eval_pending [system] [group_supervision_no_ta]
  6. ta_evaluation_entry --(ta_grades_submitted)--> qualitative_eval_pending [instructor]
  7. qualitative_eval_pending --(qualitative_submitted)--> grades_locked [instructor] [group_supervision_qualitative_in_time]
  8. qualitative_eval_pending --(sla_breach)--> qualitative_eval_delay [system] [group_supervision_qualitative_sla_breach]
- SOP step mappings (7 steps): see sop_step_mappings.json

### skills_course_completion (SOP 63)
- Name (fa): خات درس تکک تر ارتا
- Status: complete_in_metadata
- metadata: metadata/processes/skills_course_completion.json
- registry: processes/skills_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. awaiting_session_17 --(calendar_session_17_reached)--> session_17_grades_entry [system]
  2. session_17_grades_entry --(session_17_submitted)--> awaiting_session_18 [instructor] [skills_session_17_submitted_in_time]
  3. session_17_grades_entry --(sla_breach)--> session_17_delay [system] [skills_session_17_sla_breach]
  4. awaiting_session_18 --(calendar_session_18_reached)--> session_18_grades_entry [system]
  5. session_18_grades_entry --(session_18_submitted)--> ta_evaluation_entry [instructor] [skills_course_has_ta]
  6. session_18_grades_entry --(session_18_submitted)--> qualitative_eval_pending [instructor] [skills_course_no_ta]
  7. ta_evaluation_entry --(ta_grades_submitted)--> qualitative_eval_pending [instructor]
  8. qualitative_eval_pending --(qualitative_submitted)--> grades_locked [instructor] [skills_qualitative_submitted_in_time]
  9. qualitative_eval_pending --(sla_breach)--> qualitative_eval_delay [system] [skills_qualitative_sla_breach]
- SOP step mappings (13 steps): see sop_step_mappings.json

### film_observation_course_completion (SOP 64)
- Name (fa): خات ر درس ع کاربرد شاد فا  بخش آپد گزارش پاا
- Status: complete_in_metadata
- metadata: metadata/processes/film_observation_course_completion.json
- registry: processes/film_observation_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, system
- Workflow:
  1. grades_entry --(grades_submitted)--> grades_locked [instructor] [course_grades_submitted_in_time]
  2. grades_entry --(sla_breach)--> delay_reported [system] [course_grades_sla_breach]
- SOP step mappings (5 steps): see sop_step_mappings.json

### live_therapy_observation_course_completion (SOP 65)
- Name (fa): خات درس شاد زد درا  بخش آپد گزارش پاا
- Status: complete_in_metadata
- metadata: metadata/processes/live_therapy_observation_course_completion.json
- registry: processes/live_therapy_observation_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, system
- Workflow:
  1. grades_entry --(grades_submitted)--> grades_locked [instructor] [course_grades_submitted_in_time]
  2. grades_entry --(sla_breach)--> delay_reported [system] [course_grades_sla_breach]
- SOP step mappings (5 steps): see sop_step_mappings.json

### live_therapy_observation_session_prep (SOP 66)
- Name (fa): دات برگزار جسات شاد زد درا
- Status: complete_in_metadata
- metadata: metadata/processes/live_therapy_observation_session_prep.json
- registry: processes/live_therapy_observation_session_prep
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: admission_officer, therapy_education_coordinator, system
- Workflow:
  1. patient_referral --(referral_submitted)--> coordination_pending [admission_officer]
  2. coordination_pending --(time_registered)--> session_scheduled [therapy_education_coordinator] [live_session_time_agreed]
  3. coordination_pending --(no_time_agreed)--> coordination_closed [therapy_education_coordinator] [live_session_time_not_agreed]

### live_supervision_course_completion (SOP 67)
- Name (fa): خات درس سپر زد
- Status: complete_in_metadata
- metadata: metadata/processes/live_supervision_course_completion.json
- registry: processes/live_supervision_course_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: violation_registration
- Runtime chains: violation_registration
- Workflow:
  1. sessions_in_progress --(mirror_attendance_recorded)--> mirror_implementation_pending [system]
  2. mirror_implementation_pending --(mirror_write_submitted)--> sessions_in_progress [student]
  3. mirror_implementation_pending --(sla_breach)--> mirror_write_violation [system] [live_supervision_mirror_write_sla_breach]
  4. sessions_in_progress --(third_mirror_recorded)--> mirror_eval_pending [system]
  5. mirror_implementation_pending --(third_mirror_recorded)--> mirror_eval_pending [system]
  6. mirror_eval_pending --(mirror_eval_submitted)--> sessions_in_progress [instructor]
  7. mirror_eval_pending --(sla_breach)--> mirror_eval_violation [system] [live_supervision_mirror_eval_sla_breach]
  8. sessions_in_progress --(eighteenth_attendance_recorded)--> final_eval_pending [system]
  9. mirror_eval_pending --(eighteenth_attendance_recorded)--> final_eval_pending [system]
  10. final_eval_pending --(final_eval_submitted)--> completed [instructor]
  ... +1 transitions
- SOP step mappings (5 steps): see sop_step_mappings.json

### live_supervision_session_prep (SOP 68)
- Name (fa): دات برگزار جسات سپر زد
- Status: complete_in_metadata
- metadata: metadata/processes/live_supervision_session_prep.json
- registry: processes/live_supervision_session_prep
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: admission_officer, therapy_education_coordinator, system
- Workflow:
  1. patient_referral --(referral_submitted)--> coordination_pending [admission_officer]
  2. coordination_pending --(time_registered)--> session_scheduled [therapy_education_coordinator] [live_session_time_agreed]
  3. coordination_pending --(no_time_agreed)--> coordination_closed [therapy_education_coordinator] [live_session_time_not_agreed]

### article_writing_completion (SOP 69)
- Name (fa): خات درس اس جت گزارش رد
- Status: complete_in_metadata
- metadata: metadata/processes/article_writing_completion.json
- registry: processes/article_writing_completion
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, monitoring_committee_officer, course_committee_scientific, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. course_active --(completion_ticked)--> class_closed_student [instructor]
  2. class_closed_student --(defense_requested)--> instructor_eval_pending [student]
  3. class_closed_student --(sla_8days_breach)--> student_delay_violation [system] [article_student_8day_sla_breach]
  4. instructor_eval_pending --(evaluation_submitted)--> completed_to_defense [instructor]
  5. instructor_eval_pending --(sla_4days_breach)--> instructor_delay_violation [system] [article_instructor_4day_sla_breach]
  6. course_active --(enrollment_term3_plus)--> term3_violation [system] [article_enrollment_term3_plus]

### thesis_defense_request (SOP 70)
- Name (fa): درخاست ثبت دفاع پااا
- Status: complete_in_metadata
- metadata: metadata/processes/thesis_defense_request.json
- registry: processes/thesis_defense_request
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, progress_committee, supervision_committee, education_committee, instructor, system
- INDEX sub_process_refs: article_writing_completion, violation_registration
- Workflow:
  1. eligibility_check --(conditions_failed)--> conditions_not_met [student]
  2. eligibility_check --(psychotic_report_uploaded)--> progress_committee_review [student] [thesis_defense_eligibility_met]
  3. progress_committee_review --(report_rejected)--> report_rejected [progress_committee]
  4. progress_committee_review --(revision_requested)--> report_revision [progress_committee]
  5. progress_committee_review --(report_approved)--> supervision_committee_review [progress_committee]
  6. report_revision --(revision_uploaded)--> progress_committee_review [student]
  7. supervision_committee_review --(permit_denied)--> defense_permit_denied [supervision_committee]
  8. supervision_committee_review --(permit_issued)--> thesis_upload [supervision_committee]
  9. thesis_upload --(thesis_uploaded)--> education_committee_scheduling [student]
  10. education_committee_scheduling --(schedule_registered)--> first_defense_held [education_committee]
  ... +7 transitions

### upgrade_to_educational_therapist (SOP 71)
- Name (fa): ارتا ب دراگر آزش
- Status: complete_in_metadata
- metadata: metadata/processes/upgrade_to_educational_therapist.json
- registry: processes/upgrade_to_educational_therapist
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, education_committee, system
- INDEX sub_process_refs: violation_registration
- Workflow:
  1. student_start --(conditions_failed)--> eligibility_failed [student] [et_upgrade_eligibility_not_met]
  2. student_start --(conditions_met)--> monitoring_review [student] [et_upgrade_eligibility_met]
  3. monitoring_review --(rejected)--> monitoring_rejected [supervision_committee]
  4. monitoring_review --(approved)--> interview_scheduling [supervision_committee]
  5. interview_scheduling --(interview_scheduled)--> interview_held [education_committee]
  6. interview_held --(interview_rejected)--> interview_rejected [education_committee]
  7. interview_held --(interview_approved)--> therapy_readiness_check [education_committee]
  8. therapy_readiness_check --(therapy_frequency_low)--> therapy_frequency_adjustment [system] [et_therapy_frequency_below_weekly]
  9. therapy_readiness_check --(therapy_active)--> personal_therapy_hours [system] [et_therapy_active]
  10. therapy_readiness_check --(no_active_therapy)--> therapist_selection [system] [et_therapy_not_active]
  ... +14 transitions

### intern_bulk_patient_referral (SOP 72)
- Name (fa): ارجاع ک بارا اتر ب دراگرا دگر
- Status: complete_in_metadata
- metadata: metadata/processes/intern_bulk_patient_referral.json
- registry: processes/intern_bulk_patient_referral
- Registry artifacts: 04_status.md, SOP_document.txt, SOP_flowchart.png
- Roles: student, supervision_committee, therapy_committee_executor, therapy_education_coordinator, deputy_education, system
- INDEX sub_process_refs: patient_referral
- Workflow:
  1. supervision_start --(meeting_and_conditions_logged)--> referral_conditions_set [supervision_committee]
  2. referral_conditions_set --(patient_list_published)--> student_patient_log [system]
  3. student_patient_log --(student_patient_contacts_done)--> general_therapy_committee_review [student]
  4. general_therapy_committee_review --(committee_referral_notes_complete)--> coordination_followup [therapy_committee_executor]
  5. coordination_followup --(coordination_followup_complete)--> completed [therapy_education_coordinator]

### live_supervision_ta_evaluation (SOP 73)
- Name (fa): ارزاب ککدرس درس سپر زد
- Status: complete_in_metadata
- metadata: metadata/processes/live_supervision_ta_evaluation.json
- registry: processes/live_supervision_ta_evaluation
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: teaching_assistant, instructor, course_committee_scientific, system
- INDEX sub_process_refs: live_supervision_course_completion, violation_registration
- Workflow:
  1. session_18_completed --(grades_aggregated)--> evaluation_computed [system]
  2. evaluation_computed --(result_pass)--> passed [system] [live_supervision_ta_score_gte_74]
  3. evaluation_computed --(result_fail)--> failed [system] [live_supervision_ta_score_lt_74]

### live_therapy_observation_ta_attendance_completion (SOP 74)
- Name (fa): خات درس شاد زد درا  بخش کک درس  ر حضر  غاب  شارکت
- Status: complete_in_metadata
- metadata: metadata/processes/live_therapy_observation_ta_attendance_completion.json
- registry: processes/live_therapy_observation_ta_attendance_completion
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: live_therapy_observation_course_completion, violation_registration
- Workflow:
  1. grades_entry --(grades_submitted)--> grades_locked [instructor] [course_grades_submitted_in_time]
  2. grades_entry --(sla_breach)--> delay_reported [system] [course_grades_sla_breach]

### film_observation_ta_attendance_completion (SOP 75)
- Name (fa): خات ر درس ع کاربرد شاد فا  بخش کک درس  ر حضر  غاب  شارکت
- Status: complete_in_metadata
- metadata: metadata/processes/film_observation_ta_attendance_completion.json
- registry: processes/film_observation_ta_attendance_completion
- Registry artifacts: SOP_document.txt, SOP_flowchart.png
- Roles: student, instructor, teaching_assistant, course_committee_scientific, monitoring_committee_officer, system
- INDEX sub_process_refs: film_observation_course_completion, violation_registration
- Workflow:
  1. grades_entry --(grades_submitted)--> grades_locked [instructor] [course_grades_submitted_in_time]
  2. grades_entry --(sla_breach)--> delay_reported [system] [course_grades_sla_breach]

## Shared sub-processes

### patient_referral (SOP None)
- Name (fa): ارجاع بیماران انترن به درمانگران دیگر
- Status: sub_process_only
- metadata: metadata/processes/patient_referral.json
- registry: None
- Registry artifacts: SOP_document.txt (+ png where present)
- Roles: monitoring_committee_officer, system
- Workflow:
  1. referral_triggered --(list_submitted)--> patients_listed [monitoring_committee_officer]
  2. patients_listed --(assignments_done)--> therapists_assigned [monitoring_committee_officer]
  3. therapists_assigned --(notifications_done)--> notifications_sent [monitoring_committee_officer]
  4. notifications_sent --(closed)--> closed [system]
