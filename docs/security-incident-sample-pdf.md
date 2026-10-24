# Incident: real registry document committed to a public repository

`sample-data/61cee7af-7d89-43b4-bf2c-e7e5bd3804b2.PDF` (198 pages, ~11.8 MB) was committed to this public
repository. It appears to be a real company registry listing containing company names and contact details
(phone numbers and email addresses). It has been removed from the working tree and `sample-data/` is now
git-ignored except for its README. **Removal from the latest commit does not remove it from history or from
existing clones and forks.**

## Required follow-up (needs repository-owner access)

1. Treat the contact details in the file as exposed. Decide whether the data subjects or the data source's owner must be notified.
2. Purge the file from history, then force-push every branch and tag:

   ```bash
   pip install git-filter-repo
   git clone --mirror https://github.com/Victor-Kipruto-Rop/pesaguard-datasource.git
   cd pesaguard-datasource.git
   git filter-repo --invert-paths --path-glob 'sample-data/*.PDF' --path-glob 'sample-data/*.pdf'
   git push --force --mirror
   ```

3. Ask GitHub Support to run garbage collection and remove cached views/PR refs, and delete any forks you control.
4. Everyone with a clone must re-clone (or `git fetch && git reset --hard origin/main`); old clones still hold the file.
5. Keep real documents in private object storage. CI never needs them.
