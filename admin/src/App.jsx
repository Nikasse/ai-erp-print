import { useEffect, useState } from 'react'

function App() {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [transactions, setTransactions] = useState([])

  const [amount, setAmount] = useState('')
  const [type, setType] = useState('income')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState(null)

  const fetchSummary = () => {
    fetch('http://localhost:8000/api/summary')
      .then((response) => response.json())
      .then((data) => setSummary(data))
      .catch(() => setError('Не вдалося завантажити дані'))
  }

  const fetchTransactions = () => {
    fetch('http://localhost:8000/api/transactions')
      .then((response) => response.json())
      .then((data) => setTransactions(data))
      .catch(() => setTransactions([]))
  }

  useEffect(() => {
    fetchSummary()
  }, [])

  useEffect(() => {
    fetchTransactions()
  }, [])

  const handleAdd = () => {
    setFormError(null)

    fetch('http://localhost:8000/api/transactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        amount: Number(amount),
        type,
        category,
        description,
      }),
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося додати операцію')
        }
        return data
      })
      .then(() => {
        setAmount('')
        setType('income')
        setCategory('')
        setDescription('')
        fetchTransactions()
        fetchSummary()
      })
      .catch((err) => setFormError(err.message))
  }

  if (error) {
    return <p>{error}</p>
  }

  if (!summary) {
    return <p>Завантаження...</p>
  }

  return (
    <div>
      <div>
        <h2>Доходи</h2>
        <p>{summary.total_income}</p>
      </div>
      <div>
        <h2>Витрати</h2>
        <p>{summary.total_expense}</p>
      </div>
      <div>
        <h2>Баланс</h2>
        <p>{summary.balance}</p>
      </div>

      <div>
        <h3>Нова операція</h3>
        {formError && <p>{formError}</p>}
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Сума"
        />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="income">income</option>
          <option value="expense">expense</option>
        </select>
        <input
          type="text"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="Категорія"
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Опис (необов'язково)"
        />
        <button type="button" onClick={handleAdd}>
          Додати
        </button>
      </div>

      {transactions.length === 0 ? (
        <p>Немає операцій</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Тип</th>
              <th>Сума</th>
              <th>Категорія</th>
              <th>Опис</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr key={tx.id}>
                <td>{tx.created_at}</td>
                <td>{tx.type}</td>
                <td>{tx.amount}</td>
                <td>{tx.category}</td>
                <td>{tx.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App
