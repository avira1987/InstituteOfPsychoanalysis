import React, { useRef, useLayoutEffect } from 'react'
import { toFaDigits } from '../utils/persianDigits'

const ATTRS = ['title', 'aria-label', 'aria-description', 'placeholder']

function shouldSkipElement(el) {
  if (!el || el.nodeType !== Node.ELEMENT_NODE) return false
  const tag = el.tagName
  if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEMPLATE' || tag === 'NOSCRIPT') return true
  if (tag === 'SVG' || tag === 'MATH') return true
  if (tag === 'INPUT' || tag === 'TEXTAREA') return true
  if (el.getAttribute?.('data-latin-digits') != null) return true
  if (el.isContentEditable) return true
  return false
}

function convertTextNode(node) {
  const t = node.textContent
  if (!t || !/\d/.test(t)) return
  const next = toFaDigits(t)
  if (next !== t) node.textContent = next
}

function convertAttrs(el) {
  if (shouldSkipElement(el)) return
  for (const a of ATTRS) {
    const v = el.getAttribute(a)
    if (v && /\d/.test(v)) {
      const next = toFaDigits(v)
      if (next !== v) el.setAttribute(a, next)
    }
  }
}

function walk(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    const parent = node.parentElement
    if (parent && !shouldSkipElement(parent)) convertTextNode(node)
    return
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return
  const el = node
  if (shouldSkipElement(el)) return
  convertAttrs(el)
  const children = el.childNodes
  for (let i = 0; i < children.length; i++) walk(children[i])
}

/**
 * پس از رندر، متن زیرمجموعه را طوری به‌روز می‌کند که ارقام لاتین به فارسی تبدیل شوند.
 * ورودی‌ها و SVG برای جلوگیری از شکستن مقدار/ویژگی‌ها رد می‌شوند.
 */
export default function PersianDigitsBoundary({ children }) {
  const ref = useRef(null)

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    let raf = 0
    const run = () => {
      walk(root)
    }
    const schedule = () => {
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = 0
        run()
      })
    }
    schedule()
    const mo = new MutationObserver(schedule)
    mo.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    })
    return () => {
      if (raf) cancelAnimationFrame(raf)
      mo.disconnect()
    }
  }, [])

  return (
    <div ref={ref} className="persian-digits-boundary" style={{ display: 'contents' }}>
      {children}
    </div>
  )
}
