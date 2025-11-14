'use client'

import { useState, useEffect } from 'react'
import styles from './page.module.css'

export default function Home() {
  const [message, setMessage] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/hello`)
      const data = await response.json()
      setMessage(data.message)
    } catch (error) {
      console.error('Error fetching data:', error)
      setMessage('Error connecting to backend')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className={styles.main}>
      <div className={styles.container}>
        <h1>Lumen</h1>
        <p>Next.js + Flask Application</p>
        <div className={styles.card}>
          <h2>Backend Status</h2>
          {loading ? (
            <p>Connecting...</p>
          ) : (
            <p>{message}</p>
          )}
        </div>
      </div>
    </main>
  )
}
