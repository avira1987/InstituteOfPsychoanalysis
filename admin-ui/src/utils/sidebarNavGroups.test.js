import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  groupSidebarNavItems,
  inferSidebarGroupId,
  resolveSidebarGroupId,
} from './sidebarNavGroups.js'

test('inferSidebarGroupId maps common paths', () => {
  assert.equal(inferSidebarGroupId('/panel'), 'home')
  assert.equal(inferSidebarGroupId('/panel/portal/staff/admissions'), 'operations')
  assert.equal(inferSidebarGroupId('/panel/portal/committee/progress'), 'committees')
  assert.equal(inferSidebarGroupId('/panel/users'), 'admin_tools')
  assert.equal(inferSidebarGroupId('/panel/profile'), 'account')
  assert.equal(inferSidebarGroupId('/panel/finance'), 'finance_reports')
})

test('groupSidebarNavItems pins account to footer and groups the rest', () => {
  const { mainGroups, footerItems } = groupSidebarNavItems([
    { path: '/panel', label: 'داشبورد', groupId: 'home' },
    { path: '/panel/tickets', label: 'تیکت', groupId: 'home' },
    { path: '/panel/users', label: 'کاربران', groupId: 'admin_tools' },
    { path: '/panel/profile', label: 'پروفایل', groupId: 'account' },
    { path: '/panel/guide', label: 'راهنما', groupId: 'account' },
  ])
  assert.equal(footerItems.length, 2)
  assert.deepEqual(footerItems.map((i) => i.path), ['/panel/profile', '/panel/guide'])
  const ids = mainGroups.map((g) => g.id)
  assert.deepEqual(ids, ['home', 'admin_tools'])
  assert.equal(mainGroups.find((g) => g.id === 'home').items.length, 2)
})

test('resolveSidebarGroupId prefers explicit groupId', () => {
  assert.equal(
    resolveSidebarGroupId({ path: '/panel/users', groupId: 'home' }),
    'home',
  )
})
