import type { KeyValue } from '../api/types'

export function interpolate(text: string, variables: KeyValue[]): string {
  const map = new Map(
    variables.filter((v) => v.enabled && v.key).map((v) => [v.key, v.value]),
  )
  return text.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, (_, key: string) => {
    return map.has(key) ? map.get(key)! : `{{${key}}}`
  })
}
