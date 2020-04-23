To get syntax in neovim (probably similar in vim but haven't tried) copy the file `nqasm.vim` in this folder to `~/.config/nvim/syntax/` (create the folder if needed) and add the line
```sh
au BufNewFile,BufRead *.nqasm set ft=nqasm
```
to the file `~/.config/nvim/filetypes.vim`.
