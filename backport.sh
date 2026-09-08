git reset HEAD~1
rm ./backport.sh
git cherry-pick 5fb83b02e7aecb8ff6896145a3b3d7ee9c932121
echo 'Resolve conflicts and force push this branch.\n\nTo backport translations run: bin/i18n/merge-translations <release-branch>'
