import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeFieldType,
  studentFormToSchemaJson,
  SHARED_FIELD_TYPES,
} from './formFieldTypes.js'

test('normalizeFieldType maps student/operator aliases to the same canonical type', () => {
  assert.equal(normalizeFieldType('file'), 'file_upload')
  assert.equal(normalizeFieldType('file_upload'), 'file_upload')
  assert.equal(normalizeFieldType('date_picker'), 'date')
  assert.equal(normalizeFieldType('shamsi_date'), 'date')
  assert.equal(normalizeFieldType('radio_list'), 'radio')
  assert.equal(normalizeFieldType('time_picker'), 'time')
  assert.equal(normalizeFieldType('Therapist_Select'), 'therapist_select')
})

test('studentFormToSchemaJson copies fields and form chrome into schema_json', () => {
  const schema = studentFormToSchemaJson({
    code: 'leave_request',
    name_fa: 'درخواست مرخصی',
    note_fa: 'توضیح',
    visible_to: ['student'],
    fields: [{ name: 'reason', type: 'textarea', label_fa: 'دلیل' }],
  })
  assert.equal(schema.code, 'leave_request')
  assert.equal(schema.name_fa, 'درخواست مرخصی')
  assert.equal(schema.fields.length, 1)
  assert.equal(schema.fields[0].name, 'reason')
  assert.deepEqual(schema.visible_to, ['student'])
})

test('shared field types cover the metadata types both audiences render', () => {
  for (const t of ['text', 'file_upload', 'step_otp', 'therapist_slot_picker', 'checkbox_list']) {
    assert.ok(SHARED_FIELD_TYPES.includes(t), t)
  }
})
