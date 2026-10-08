import { useEffect, useState } from 'react'
import { fileUrl } from './api'

/** Signed URL for a project file, or null while loading / when `name` is null. */
export function useFileUrl(projectId, name) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let cancelled = false
    if (!name) return undefined
    fileUrl(projectId, name)
      .then((u) => !cancelled && setUrl(u))
      .catch(() => !cancelled && setUrl(null))
    return () => { cancelled = true }
  }, [projectId, name])
  return name ? url : null
}
