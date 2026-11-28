import { Link } from 'react-router'

import { AuthCard } from '@auth-kit/react/ui'

export default function IntrouvablePage() {
  return (
    <AuthCard title="Page introuvable" subtitle="Cette adresse ne correspond à aucune page." icon="search">
      <Link to="/" className="ak-btn ak-btn--primary ak-btn--block">Retour à l'accueil</Link>
    </AuthCard>
  )
}
