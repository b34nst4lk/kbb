# Browser Test Coverage — User Flow Mapping

This document maps every user flow in kbb_web to the browser tests that cover it. Each flow lists its entry point, preconditions, DOM targets, and test cases.

## Flow 1: First-Time Setup

**Entry point**: `/` → `/profile`
**Preconditions**: No profile exists
**DOM targets**: `#profile-area`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/` | Dashboard shows "Get Started" card | `test_setup_flow::TestFirstTimeSetup::test_dashboard_no_profile` |
| 2 | Click "Set Up Profile" | `/profile` loads with empty state | `test_setup_flow::TestFirstTimeSetup::test_profile_page_empty_state` |
| 3 | Click "Set Up Profile" button | `#profile-area` swaps to editor | `test_setup_flow::TestFirstTimeSetup::test_profile_editor_loads` |
| 4 | Click "Cancel" | `#profile-area` returns to empty state | `test_setup_flow::TestFirstTimeSetup::test_profile_editor_cancel` |
| 5 | Fill textarea, click "Save Profile" | `#profile-area` shows profile view with success alert | `test_setup_flow::TestFirstTimeSetup::test_profile_editor_save` |
| 6 | Save fails (LLM error) | Editor re-renders with error, text preserved | `test_setup_flow::TestFirstTimeSetup::test_profile_editor_error_preserves_text` |
| 7 | After profile setup, visit `/` | Dashboard shows "Next Step" card | `test_setup_flow::TestFirstTimeSetup::test_dashboard_after_profile_setup` |

## Flow 2: Daily Question & Answer

**Entry point**: `/daily`
**Preconditions**: Profile exists (for question generation)
**DOM targets**: `#question-area`, `#response-area`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/daily` (no question) | Shows "Generate Question" button | `test_daily_qa_flow::TestDailyQA::test_daily_page_no_pending_question` |
| 2 | Click "Generate Question" | `#question-area` swaps to question card | `test_daily_qa_flow::TestDailyQA::test_generate_question` |
| 3 | Question card renders | Shows text, topic, rationale, response form | `test_daily_qa_flow::TestDailyQA::test_question_card_shows_fields` |
| 4 | Type response, click "Record Response" | `#response-area` swaps to success result | `test_daily_qa_flow::TestDailyQA::test_submit_response` |
| 5 | Success result shows links | "Answer Another" and "View Logs" links visible | `test_daily_qa_flow::TestDailyQA::test_response_result_links` |
| 6 | After HTMX swap | Response textarea receives focus | `test_daily_qa_flow::TestDailyQA::test_auto_focus_after_swap` |
| 7 | Generate question without profile | `#question-area` shows error alert | `test_daily_qa_flow::TestDailyQA::test_generate_question_no_profile` |
| 8 | Submit response fails (LLM error) | `#response-area` shows error alert | `test_daily_qa_flow::TestDailyQA::test_response_submission_error` |

## Flow 3: Profile Editing

**Entry point**: `/profile`
**Preconditions**: Profile exists
**DOM targets**: `#profile-area`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/profile` (has profile) | Shows "Structured Data" card | `test_profile_flow::TestProfileEditing::test_profile_view_shows_structured_data` |
| 2 | Click "Edit Profile" | `#profile-area` swaps to editor with current text | `test_profile_flow::TestProfileEditing::test_edit_profile_button` |
| 3 | Edit text, click "Save Profile" | Returns to view with success alert | `test_profile_flow::TestProfileEditing::test_save_edited_profile` |
| 4 | Click "Refresh Structured View" | Profile re-parsed via LLM, view updated | `test_profile_flow::TestProfileEditing::test_refresh_structured_view` |
| 5 | Refresh fails (LLM error) | Error alert appears | `test_profile_flow::TestProfileEditing::test_refresh_structured_view_error` |

## Flow 4: Knowledge Import

**Entry point**: `/knowledge/import`
**Preconditions**: None
**DOM targets**: `#import-result`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/knowledge/import` | Form renders with title, topic, content | `test_import_flow::TestKnowledgeImport::test_import_form_renders` |
| 2 | Fill fields, click "Import" | `#import-result` shows knowledge card | `test_import_flow::TestKnowledgeImport::test_import_submit_success` |

Error path is covered by HTTP-level tests in `test_partials.py::TestKnowledgeImport`.

## Flow 5: Settings Update

**Entry point**: `/settings`
**Preconditions**: None
**DOM targets**: `#settings-area`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/settings` | Form renders with all fields | `test_settings_flow::TestSettingsUpdate::test_settings_form_renders` |
| 2 | Change field, click "Save Settings" | `#settings-area` swaps to success message | `test_settings_flow::TestSettingsUpdate::test_save_settings_success` |
| 3 | Submit invalid provider | Error alert with valid options | `test_settings_flow::TestSettingsUpdate::test_save_settings_invalid_provider` |

## Flow 6: Daily Logs Browsing

**Entry point**: `/daily/logs`
**Preconditions**: None (empty state); profile + answer (for entries)
**DOM targets**: `#log-list`, date picker

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Visit `/daily/logs` (no logs) | Shows empty state | `test_logs_flow::TestDailyLogs::test_logs_list_empty` |
| 2 | After recording a response | Log list shows date links | `test_logs_flow::TestDailyLogs::test_logs_list_with_entries` |
| 3 | Click date link | Shows log detail page | `test_logs_flow::TestDailyLogs::test_log_detail_page` |
| 4 | Visit `/daily/logs/not-a-date` | Shows error page | `test_logs_flow::TestDailyLogs::test_invalid_date_page` |

## Flow 7: Transcription

**Entry point**: `/daily` (question card)
**Preconditions**: Profile exists (for question generation)
**DOM targets**: `[data-voice-recorder]`, `#audio-upload`, `/api/transcribe`

| Step | Action | Expected DOM Change | Test Case |
|------|--------|--------------------|-----------|
| 1 | Generate question | Voice recorder button present | `test_transcription_flow::TestTranscription::test_voice_recorder_button_present` |
| 2 | Generate question | Audio upload input present | `test_transcription_flow::TestTranscription::test_audio_upload_input_present` |
| 3 | POST `/api/transcribe` with valid audio | Returns `{text: "..."}` | `test_transcription_flow::TestTranscription::test_transcribe_api_endpoint` |
| 4 | POST `/api/transcribe` without file | Returns 422 | `test_transcription_flow::TestTranscription::test_transcribe_api_no_file` |
| 5 | POST `/api/transcribe` with .txt file | Returns 400 | `test_transcription_flow::TestTranscription::test_transcribe_api_unsupported_format` |

## Cross-Cutting: Navigation

**Entry point**: All pages
**DOM targets**: `nav`

| Page | Test Case |
|------|-----------|
| Dashboard (`/`) | `test_cross_cutting::TestNavigation::test_nav_links_on_dashboard` |
| Daily (`/daily`) | `test_cross_cutting::TestNavigation::test_nav_links_on_daily` |
| Knowledge (`/knowledge`) | `test_cross_cutting::TestNavigation::test_nav_links_on_knowledge` |
| Profile (`/profile`) | `test_cross_cutting::TestNavigation::test_nav_links_on_profile` |
| Settings (`/settings`) | `test_cross_cutting::TestNavigation::test_nav_links_on_settings` |

## Test Summary

| Test File | Tests |
|-----------|-------|
| `test_infra.py` | 3 |
| `test_setup_flow.py` | 7 |
| `test_daily_qa_flow.py` | 8 |
| `test_profile_flow.py` | 5 |
| `test_import_flow.py` | 2 |
| `test_settings_flow.py` | 3 |
| `test_logs_flow.py` | 4 |
| `test_transcription_flow.py` | 5 |
| `test_cross_cutting.py` | 5 |
| **Total** | **42** |