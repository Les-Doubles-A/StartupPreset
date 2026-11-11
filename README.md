# StartupPreset Manager

Dépôt GitHub : **https://github.com/Les-Doubles-A/StartupPreset**

Application de bureau (Python + PySide6) permettant de définir un preset
d'applications et de sites web à lancer automatiquement selon le jour de
la semaine, avec intégration optionnelle au démarrage de Windows.

## 1. Pourquoi PySide6 ?

- Léger : pas de moteur Chromium embarqué (contrairement à Electron).
- Accès natif au registre Windows via `winreg` (module standard de Python),
  donc aucune dépendance supplémentaire pour gérer le démarrage automatique.
- Compilable en un seul `.exe` autonome avec PyInstaller.

## 2. Installation (mode développement)

Prérequis : Python 3.10 ou supérieur installé sur Windows.

```bash
# 1. Se placer dans le dossier du projet
cd StartupPreset

# 2. (Recommandé) Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python main.py
```

## 3. Utilisation

### Gérer plusieurs presets

- La liste **"Presets"** en haut de la fenêtre affiche tous vos presets
  nommés (ex : "Boulot", "Cours du mardi", "Soirée gaming").
- **Nouveau preset** : demande un nom, crée un preset vide et l'affiche.
- **Renommer** : renomme le preset actuellement sélectionné.
- **Supprimer** : supprime le preset sélectionné (impossible s'il n'en
  reste qu'un seul — il en faut toujours au moins un).
- Cliquer sur un preset dans la liste charge son contenu (applications,
  sites, jours) dans les panneaux ci-dessous. Vos modifications en cours
  sont automatiquement conservées en mémoire quand vous changez de preset,
  mais **rien n'est écrit sur le disque tant que vous n'avez pas cliqué
  sur "Sauvegarder tous les presets"**.

### Éditer le preset sélectionné

1. **Applications** : cliquez sur "Parcourir… (.exe)" pour ajouter un
   exécutable à la liste. Décochez une ligne pour la désactiver sans la
   supprimer.
2. **Sites web** : entrez une URL dans le champ de texte et cliquez sur
   "Ajouter" (ou appuyez sur Entrée).
3. **Jours de déclenchement** : cochez les jours où CE preset doit se
   déclencher automatiquement au démarrage de Windows. Chaque preset a ses
   propres jours — deux presets peuvent très bien se déclencher le même
   jour.
4. **Tester le lancement** : lance immédiatement les applications et URL
   du preset affiché à l'écran, sans tenir compte du jour actuel — utile
   pour vérifier que tout fonctionne.

### Démarrage automatique (réglage global)

Cochez "Lancer cette application au démarrage de Windows" puis cliquez
sur **Sauvegarder tous les presets**. Une entrée est alors ajoutée dans
le registre Windows
(`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`).
Ce réglage est global : une seule entrée de démarrage pilote tous vos
presets, chacun étant filtré par ses propres jours.

### Sauvegarder

Le bouton **"Sauvegarder tous les presets"** écrit l'intégralité de vos
presets (y compris celui en cours d'édition) dans
`%APPDATA%\StartupPreset\config.json`, et applique le choix de démarrage
automatique.

### Comportement au démarrage de Windows

Au démarrage de session, Windows exécute l'application avec l'argument
`--autostart`. Dans ce mode, **aucune fenêtre ne s'affiche** : le script
parcourt **tous les presets**, lance les applications/URL de chaque
preset dont le jour actuel fait partie des jours cochés, puis se ferme
immédiatement.

## 4. Compiler en .exe autonome (optionnel)

Pour ne plus dépendre d'un interpréteur Python installé sur la machine :

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name StartupPreset main.py
```

L'exécutable généré se trouve dans `dist\StartupPreset.exe`. Si vous avez
déjà activé le démarrage automatique avec la version `python main.py`,
décochez puis recochez la case dans l'application compilée pour que le
registre pointe vers le bon exécutable (`.exe` au lieu de `pythonw.exe`).

## 5. Fichier de configuration

Le preset est stocké en JSON ici :

```
%APPDATA%\StartupPreset\config.json
```

Exemple de contenu (format multi-presets) :

```json
{
  "presets": [
    {
      "name": "Boulot",
      "apps": [
        {"path": "C:\\Program Files\\Discord\\Update.exe", "enabled": true}
      ],
      "urls": [
        {"url": "https://mail.google.com", "enabled": true}
      ],
      "days": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    },
    {
      "name": "Soirée gaming",
      "apps": [
        {"path": "C:\\Riot Games\\League of Legends.exe", "enabled": true}
      ],
      "urls": [],
      "days": ["Vendredi", "Samedi"]
    }
  ],
  "autostart": true
}
```

Vous pouvez éditer ce fichier manuellement si besoin (l'application le
relira au prochain lancement). Si vous aviez un ancien fichier de config
(format à preset unique, sans nom), il est **automatiquement migré** vers
ce nouveau format au premier chargement.

## 6. Désinstaller / désactiver le démarrage automatique

Dans l'application, décochez la case "Lancer cette application au
démarrage de Windows" puis cliquez sur "Sauvegarder". Cela supprime
proprement l'entrée du registre.

<!-- installeur-release -->
## Installation

Téléchargez **`StartupPreset-Setup-1.0.1.exe`** depuis la [dernière release](https://github.com/Les-Doubles-A/StartupPreset/releases/latest), puis lancez-le.

L'installation se fait pour l'utilisateur courant, sans droits administrateur (par défaut dans `%LOCALAPPDATA%\Programs\StartupPreset`), avec un raccourci dans le menu Démarrer et une désinstallation depuis les Paramètres Windows.

L'installeur n'est pas signé : si Windows SmartScreen l'affiche, cliquez sur « Informations complémentaires » puis « Exécuter quand même ».

### Recréer l'installeur

Compiler l'application (`pyinstaller StartupPreset.spec`), puis lancer [Inno Setup 6](https://jrsoftware.org/isinfo.php) : `iscc installer\StartupPreset.iss`. Le setup est créé dans `installer\Output\`.
