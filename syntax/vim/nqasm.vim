" Vim syntax file
" Language:	NetQASM
" Maintainer:	Axel Dahlberg <axel.dahlberg12@gmail.com>
" Last Change:	2020 Apr 04

" Based on asm.vim

" quit when a syntax file was already loaded
if exists("b:current_syntax")
  finish
endif

let s:cpo_save = &cpo
set cpo&vim
"""""""""""""""""""""""""""""""""""
" Matches
"""""""""""""""""""""""""""""""""""

" Numbers
syn match decNumber		"0\+[1-7]\=[\t\n$,; ]"
syn match decNumber		"[1-9]\d*"
syn match octNumber		"0[0-7][0-7]\+"
syn match hexNumber		"0[xX][0-9a-fA-F]\+"
syn match binNumber		"0[bB][0-1]*"

syn keyword nqasmTodo		contained TODO

syn match nqasmLabel		"[A-Za-z][A-Za-z0-9_]*"
syn match nqasmInstr		"^[a-z][a-z_]*"
syn match nqasmMacro		"[A-Za-z][0-9A-Za-z_]*\!"
syn match nqasmRegister		"[A-Z][0-9][0-9]*"
syn match nqasmBranchLabel	"[A-Za-z][A-Za-z0-9_]*:"
syn match nqasmPreamble		"# [A-Z]* .*"
syn match nqasmComment		"// .*" contains=nqasmTodo
syn region nqasmComment		start="/\*" end="\*/" contains=nqasmTodo

"""""""""""""""""""""""""""""""""""
" Categories
"""""""""""""""""""""""""""""""""""
hi def link hexNumber		Number
hi def link decNumber		Number
hi def link octNumber		Number
hi def link binNumber		Number

hi def link nqasmTodo		Todo

hi def link nqasmInstr		Keyword
hi def link nqasmLabel		Label
hi def link nqasmMacro		Macro
hi def link nqasmRegister	Operator
hi def link nqasmBranchLabel	Label
hi def link nqasmPreamble	Include
hi def link nqasmComment	Comment

"""""""""""""""""""""""""""""""""""
" Colors
"""""""""""""""""""""""""""""""""""

highlight Keyword		cterm=bold ctermfg=Green guifg=Green
highlight Label			cterm=bold ctermfg=Yellow guifg=Yellow
highlight Macroc		term=bold ctermfg=DarkYellow guifg=DarkYellow
highlight Operator		ctermfg=Red guifg=Red
highlight Include		ctermfg=DarkBlue guifg=DarkBlue
highlight Comment		ctermfg=Gray guifg=Gray


let b:current_syntax = "nqasm"

let &cpo = s:cpo_save
unlet s:cpo_save
