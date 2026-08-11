import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  filterContextForOperators,
  OPERATOR_HIDDEN_CONTEXT_KEYS,
  INTERVIEWER_USER_CONTEXT_KEYS,
} from './operatorContextFilter.js'

test('filterContextForOperators removes integration and ui_hints keys', () => {
  const ctx = {
    notes: 'یادداشت',
    integration_events: [{ type: 'x' }],
    ui_hints: { foo: 1 },
  }
  const out = filterContextForOperators(ctx)
  assert.equal(out.notes, 'یادداشت')
  assert.equal(out.integration_events, undefined)
  assert.equal(out.ui_hints, undefined)
})

test('filterContextForOperators hides *_id when label alternative exists', () => {
  const ctx = {
    therapist_id: 'uuid-1',
    selected_therapist_label: 'دکتر احمدی',
    supervisor_id: 'uuid-2',
  }
  const out = filterContextForOperators(ctx)
  assert.equal(out.therapist_id, undefined)
  assert.equal(out.selected_therapist_label, 'دکتر احمدی')
  assert.equal(out.supervisor_id, undefined)
})

test('filterContextForOperators hides unknown *_id keys', () => {
  const ctx = {
    custom_party_id: 'uuid-9',
    notes: 'توضیح',
  }
  const out = filterContextForOperators(ctx)
  assert.equal(out.custom_party_id, undefined)
  assert.equal(out.notes, 'توضیح')
})

test('filterContextForOperators technical mode returns full copy', () => {
  const ctx = {
    therapist_id: 'uuid-1',
    integration_events: [],
    ui_hints: {},
  }
  const out = filterContextForOperators(ctx, { technical: true })
  assert.equal(out.therapist_id, 'uuid-1')
  assert.deepEqual(out.integration_events, [])
  assert.deepEqual(out.ui_hints, {})
})

test('filterContextForOperators hides parent and payload keys', () => {
  const ctx = {
    parent_instance_id: 'p1',
    payload: { raw: true },
    amount: 1000,
  }
  const out = filterContextForOperators(ctx)
  assert.equal(out.parent_instance_id, undefined)
  assert.equal(out.payload, undefined)
  assert.equal(out.amount, 1000)
})

test('OPERATOR_HIDDEN_CONTEXT_KEYS includes known technical keys', () => {
  assert.ok(OPERATOR_HIDDEN_CONTEXT_KEYS.includes('integration_events'))
  assert.ok(OPERATOR_HIDDEN_CONTEXT_KEYS.includes('ui_hints'))
})

test('filterContextForOperators keeps useful form/document internal keys', () => {
  const ctx = {
    __student_forms_submitted_states: { documents_upload: true },
    __document_field_status: { photo: 'approved' },
    __secret_debug: { x: 1 },
  }
  const out = filterContextForOperators(ctx)
  assert.deepEqual(out.__student_forms_submitted_states, { documents_upload: true })
  assert.deepEqual(out.__document_field_status, { photo: 'approved' })
  assert.equal(out.__secret_debug, undefined)
})

test('filterContextForOperators hides selected_timeslot and transition crumbs', () => {
  const ctx = {
    selected_timeslot: 'uuid-slot',
    from_state: 'interview_payment',
    to_state: 'interview_completed',
    interview_date: '1404-01-01',
    interview_location_or_link: 'آنلاین',
  }
  const out = filterContextForOperators(ctx)
  assert.equal(out.selected_timeslot, undefined)
  assert.equal(out.from_state, undefined)
  assert.equal(out.to_state, undefined)
  assert.equal(out.interview_date, '1404-01-01')
  assert.equal(out.interview_location_or_link, 'آنلاین')
})

test('filterContextForOperators interviewer audience keeps only user interview fields', () => {
  const ctx = {
    interview_date: '1404-01-01',
    interview_time: '10:00',
    interview_result: 'full_admission',
    interviewer_notes: 'یادداشت',
    selected_timeslot: 'uuid-slot',
    photo: { url: '/x' },
    amount: 1000,
    __document_field_status: { photo: 'approved' },
    notes: 'رزرو از طریق اسلات سامانه',
  }
  const out = filterContextForOperators(ctx, { audience: 'interviewer' })
  assert.equal(out.interview_date, '1404-01-01')
  assert.equal(out.interview_time, '10:00')
  assert.equal(out.interview_result, 'full_admission')
  assert.equal(out.interviewer_notes, 'یادداشت')
  assert.equal(out.selected_timeslot, undefined)
  assert.equal(out.photo, undefined)
  assert.equal(out.amount, undefined)
  assert.equal(out.__document_field_status, undefined)
  assert.equal(out.notes, undefined)
  assert.ok(INTERVIEWER_USER_CONTEXT_KEYS.has('interview_result'))
})
