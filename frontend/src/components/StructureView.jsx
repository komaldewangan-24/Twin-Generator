import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import Pins from './Pins'
import { Spinner } from './ui'

const FLAG = 0xff5a1f

/** Parse backend/app/services/structure.py's file: "TWSP", count, float32 xyz, uint8 rgb. */
function parsePoints(buffer) {
  const head = new DataView(buffer)
  const magic = String.fromCharCode(head.getUint8(0), head.getUint8(1), head.getUint8(2), head.getUint8(3))
  if (magic !== 'TWSP') throw new Error('This is not a 3D structure file.')
  const n = head.getUint32(4, true)
  return {
    n,
    xyz: new Float32Array(buffer, 8, n * 3),
    rgb: new Uint8Array(buffer, 8 + n * 12, n * 3),
  }
}

const median = (arr) => {
  const b = Float32Array.from(arr).sort()
  return b[Math.floor(b.length / 2)]
}

/** Median centre and a percentile radius, so stray points far outside the room do not shrink the view. */
function bounds({ n, xyz }) {
  const step = Math.max(1, Math.floor(n / 8000))
  const xs = [], ys = [], zs = []
  for (let i = 0; i < n; i += step) {
    xs.push(xyz[i * 3]); ys.push(xyz[i * 3 + 1]); zs.push(xyz[i * 3 + 2])
  }
  const c = new THREE.Vector3(median(xs), median(ys), median(zs))
  const d = xs.map((x, i) => Math.hypot(x - c.x, ys[i] - c.y, zs[i] - c.z)).sort((a, b) => a - b)
  return { center: c, radius: Math.max(d[Math.floor(d.length * 0.85)], 0.25) }
}

function lineSegments(positions, color, opacity = 1) {
  const g = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }))
}

/** Room as walls: floor outline, ceiling outline and a handful of vertical edges. */
function roomBox(box) {
  const group = new THREE.Group()
  const loop = (pts) => {
    const out = []
    for (let i = 0; i < pts.length; i++) out.push(...pts[i], ...pts[(i + 1) % pts.length])
    return out
  }
  // faint floor so the room has ground under it (the outline is convex, so a fan of triangles fills it)
  const fan = []
  for (let i = 1; i < box.floor.length - 1; i++) fan.push(...box.floor[0], ...box.floor[i], ...box.floor[i + 1])
  const floor = new THREE.Mesh(
    new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(fan, 3)),
    new THREE.MeshBasicMaterial({ color: FLAG, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false }),
  )
  group.add(floor)
  group.add(lineSegments(loop(box.floor), FLAG, 1))
  group.add(lineSegments(loop(box.ceiling), 0xe9eef1, 0.55))
  const every = Math.max(1, Math.round(box.floor.length / 10))
  const verticals = []
  for (let i = 0; i < box.floor.length; i += every) verticals.push(...box.floor[i], ...box.ceiling[i])
  group.add(lineSegments(verticals, 0xe9eef1, 0.3))
  return group
}

/** The phone's path: a line plus a small camera icon at each sampled pose. */
function cameraPath(tour, up, size) {
  const group = new THREE.Group()
  const upV = new THREE.Vector3(...up).normalize()
  const lines = []
  const icons = []
  tour.forEach((pose, i) => {
    const p = new THREE.Vector3(...pose.position)
    if (i > 0) lines.push(...tour[i - 1].position, ...pose.position)
    if (i % 2) return
    const f = new THREE.Vector3(...pose.forward).normalize()
    const r = new THREE.Vector3().crossVectors(f, upV).normalize()
    const u = new THREE.Vector3().crossVectors(r, f).normalize()
    const centre = p.clone().addScaledVector(f, size)
    const corners = [
      centre.clone().addScaledVector(r, size * 0.6).addScaledVector(u, size * 0.4),
      centre.clone().addScaledVector(r, -size * 0.6).addScaledVector(u, size * 0.4),
      centre.clone().addScaledVector(r, -size * 0.6).addScaledVector(u, -size * 0.4),
      centre.clone().addScaledVector(r, size * 0.6).addScaledVector(u, -size * 0.4),
    ]
    corners.forEach((c, k) => {
      icons.push(...p.toArray(), ...c.toArray())                       // apex to corner
      icons.push(...c.toArray(), ...corners[(k + 1) % 4].toArray())    // image rectangle
    })
  })
  group.add(lineSegments(lines, FLAG, 0.35))
  group.add(lineSegments(icons, FLAG, 0.8))
  return group
}

/** Objects: a diamond at each detected object, with a drop line to the floor. */
function objectMarkers(pins, up, floorHeight, size) {
  const group = new THREE.Group()
  const upV = new THREE.Vector3(...up).normalize()
  const geometry = new THREE.OctahedronGeometry(size, 0)
  const material = new THREE.MeshBasicMaterial({ color: FLAG })
  const drops = []
  for (const pin of pins) {
    const w = new THREE.Vector3(...pin.world)
    const m = new THREE.Mesh(geometry, material)
    m.position.copy(w)
    group.add(m)
    const onFloor = w.clone().addScaledVector(upV, floorHeight - w.dot(upV))
    drops.push(...w.toArray(), ...onFloor.toArray())
  }
  group.add(lineSegments(drops, FLAG, 0.7))
  return group
}

export default function StructureView({ url, recon, pins = [], showPins = true, resetKey = 0, onError, onSurface }) {
  const host = useRef(null)
  const cameraRef = useRef(null)
  const frameRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [count, setCount] = useState(0)
  const [message, setMessage] = useState('')
  const surfaceRef = useRef(onSurface)
  surfaceRef.current = onSurface

  useEffect(() => {
    if (!url || !host.current) return undefined
    let cancelled = false
    let raf = 0
    let renderer = null
    let controls = null
    let ro = null
    const disposables = []
    const el = host.current

    ;(async () => {
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`The structure file could not be loaded (${res.status}).`)
        const data = parsePoints(await res.arrayBuffer())
        if (cancelled) return

        const scene = new THREE.Scene()
        scene.background = new THREE.Color(0x0b141c)
        const up = recon?.up ?? [0, 1, 0]
        const unitsPerMeter = recon?.meters_per_unit ? 1 / recon.meters_per_unit : 1

        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.BufferAttribute(data.xyz, 3))
        geometry.setAttribute('color', new THREE.BufferAttribute(data.rgb, 3, true))
        const points = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 2.6, sizeAttenuation: false, vertexColors: true }))
        scene.add(points)
        disposables.push(geometry, points.material)

        const floorH = recon?.room_box ? new THREE.Vector3(...recon.room_box.floor[0]).dot(new THREE.Vector3(...up).normalize()) : 0
        if (recon?.room_box?.floor?.length > 2) scene.add(roomBox(recon.room_box))
        if (recon?.tour?.length > 1) scene.add(cameraPath(recon.tour, up, 0.22 * unitsPerMeter))
        if (pins.length) scene.add(objectMarkers(pins, up, floorH, 0.07 * unitsPerMeter))

        const { center, radius } = bounds(data)
        const camera = new THREE.PerspectiveCamera(50, 1, radius * 0.01, radius * 40)
        camera.up.set(...up).normalize()
        cameraRef.current = camera

        renderer = new THREE.WebGLRenderer({ antialias: true })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
        el.appendChild(renderer.domElement)
        renderer.domElement.style.display = 'block'
        renderer.domElement.setAttribute('aria-label', '3D structure recovered from the video')

        controls = new OrbitControls(camera, renderer.domElement)
        controls.enableDamping = true

        // A 3/4 overview from above, like looking into a dolls' house.
        const frame = () => {
          const upV = camera.up.clone()
          const helper = Math.abs(upV.x) > 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0)
          const side = new THREE.Vector3().crossVectors(upV, helper).normalize()
          const side2 = new THREE.Vector3().crossVectors(upV, side).normalize()
          camera.position.copy(center).addScaledVector(side, radius * 2.0).addScaledVector(side2, radius * 1.3).addScaledVector(upV, radius * 1.5)
          controls.target.copy(center)
          camera.lookAt(center)
          controls.update()
        }
        frameRef.current = frame
        frame()

        const resize = () => {
          const w = el.clientWidth || 1
          const h = el.clientHeight || 1
          renderer.setSize(w, h)
          camera.aspect = w / h
          camera.updateProjectionMatrix()
        }
        resize()
        ro = new ResizeObserver(resize)
        ro.observe(el)

        // For the Measure tool: the point nearest the click (within a few pixels), preferring the one
        // in front. Points are a sparse sample of the surface, so "nearest on screen" is what feels right.
        const ndc = new THREE.Vector3()
        const pickPoint = (clientX, clientY) => {
          const rect = renderer.domElement.getBoundingClientRect()
          const sx = clientX - rect.left
          const sy = clientY - rect.top
          camera.updateMatrixWorld()
          let best = -1
          let bestDepth = Infinity
          for (let i = 0; i < data.n; i++) {
            ndc.set(data.xyz[i * 3], data.xyz[i * 3 + 1], data.xyz[i * 3 + 2]).project(camera)
            if (ndc.z < -1 || ndc.z > 1) continue
            const dx = ((ndc.x + 1) / 2) * rect.width - sx
            const dy = ((1 - ndc.y) / 2) * rect.height - sy
            if (dx * dx + dy * dy <= 100 && ndc.z < bestDepth) { best = i; bestDepth = ndc.z }
          }
          return best < 0 ? null : [data.xyz[best * 3], data.xyz[best * 3 + 1], data.xyz[best * 3 + 2]]
        }
        surfaceRef.current?.({ camera, canvas: renderer.domElement, pick: pickPoint })

        const loop = () => {
          controls.update()
          renderer.render(scene, camera)
          raf = requestAnimationFrame(loop)
        }
        loop()
        setCount(data.n)
        setStatus('ready')
      } catch (err) {
        if (cancelled) return
        console.error('[StructureView]', err)
        setMessage(err?.message || String(err))
        setStatus('error')
        onError?.(err)
      }
    })()

    return () => {
      cancelled = true
      surfaceRef.current?.(null)
      cancelAnimationFrame(raf)
      ro?.disconnect()
      controls?.dispose()
      disposables.forEach((d) => d.dispose?.())
      if (renderer) {
        renderer.dispose()
        renderer.domElement.remove()
      }
      cameraRef.current = null
      frameRef.current = null
    }
    // pins and recon only change when the scan changes, which remounts the viewer
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  useEffect(() => {
    if (resetKey) frameRef.current?.()
  }, [resetKey])

  const viewerLike = useRef({})
  viewerLike.current = { camera: cameraRef.current }

  return (
    <div ref={host} className="absolute inset-0 overflow-hidden">
      {status === 'loading' && (
        <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center text-[#9db0be]">
          <span className="flex flex-col items-center gap-2"><Spinner className="h-7 w-7 text-flag" /> Loading the 3D structure…</span>
        </div>
      )}
      {status === 'error' && (
        <div role="alert" className="absolute inset-0 z-10 grid place-items-center p-6 text-center text-[#f3b9a6]">{message}</div>
      )}
      {status === 'ready' && showPins && pins.length > 0 && <Pins viewerRef={viewerLike} pins={pins} />}
      {status === 'ready' && (
        <ul className="pointer-events-none absolute bottom-4 right-5 z-10 space-y-1 text-right font-mono text-[11px] uppercase tracking-wider text-[#9db0be]">
          <li><span className="text-paper">{count.toLocaleString()}</span> points from the video</li>
          <li><span className="text-flag">■</span> room · camera path · objects</li>
        </ul>
      )}
    </div>
  )
}
