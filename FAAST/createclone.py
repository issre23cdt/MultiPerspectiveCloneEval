import os
import random
import javalang
import javalang.tree
import javalang.ast
import javalang.util
from javalang.ast import Node
import torch
from anytree import AnyNode, RenderTree

from createclone_java import getedge_nextsib, getedge_flow, getedge_nextstmt, getedge_nexttoken, getedge_nextuse
from create_data import get_train_test_data

def get_token(node):
    token = ''
    # print(isinstance(node, Node))
    # print(type(node))
    if isinstance(node, str):
        token = node
    elif isinstance(node, set):
        token = 'Modifier'
    elif isinstance(node, Node):
        token = node.__class__.__name__
    # print(node.__class__.__name__,str(node))
    # print(node.__class__.__name__, node)
    return token


def get_child(root):
    # print(root)
    if isinstance(root, Node):
        children = root.children
    elif isinstance(root, set):
        children = list(root)
    else:
        children = []

    def expand(nested_list):
        for item in nested_list:
            if isinstance(item, list):
                for sub_item in expand(item):
                    # print(sub_item)
                    yield sub_item
            elif item:
                # print(item)
                yield item

    return list(expand(children))


def get_sequence(node, sequence):
    token, children = get_token(node), get_child(node)
    sequence.append(token)
    # print(len(sequence), token)
    for child in children:
        get_sequence(child, sequence)


def getnodes(node, nodelist):
    nodelist.append(node)
    children = get_child(node)
    for child in children:
        getnodes(child, nodelist)


def createtree(root, node, nodelist, parent=None):
    id = len(nodelist)
    # print(id)
    token, children = get_token(node), get_child(node)
    if id == 0:
        root.token = token
        root.data = node
    else:
        newnode = AnyNode(id=id, token=token, data=node, parent=parent)
    nodelist.append(node)
    for child in children:
        if id == 0:
            createtree(root, child, nodelist, parent=root)
        else:
            createtree(root, child, nodelist, parent=newnode)


def getnodeandedge_astonly(node, nodeindexlist, vocabdict, src, tgt):
    token = node.token
    nodeindexlist.append([vocabdict[token]])
    for child in node.children:
        src.append(node.id)
        tgt.append(child.id)
        src.append(child.id)
        tgt.append(node.id)
        getnodeandedge_astonly(child, nodeindexlist, vocabdict, src, tgt)


def getnodeandedge(node, nodeindexlist, vocabdict, src, tgt, edgetype):
    token = node.token
    nodeindexlist.append([vocabdict[token]])
    for child in node.children:
        src.append(node.id)
        tgt.append(child.id)
        edgetype.append([0])
        src.append(child.id)
        tgt.append(node.id)
        edgetype.append([0])
        getnodeandedge(child, nodeindexlist, vocabdict, src, tgt, edgetype)


def countnodes(node, ifcount, whilecount, forcount, blockcount):
    token = node.token
    if token == 'IfStatement':
        ifcount += 1
    if token == 'WhileStatement':
        whilecount += 1
    if token == 'ForStatement':
        forcount += 1
    if token == 'BlockStatement':
        blockcount += 1
    print(ifcount, whilecount, forcount, blockcount)
    for child in node.children:
        countnodes(child, ifcount, whilecount, forcount, blockcount)


def createast(flist):
    asts = []
    paths = []
    alltokens = []
    err = []
    for file in flist:
        if not os.path.exists(file):
            err.append(file)
            continue
        try:
            programfile = open(file, encoding='utf-8')
            programtext = programfile.read()
            programtokens = javalang.tokenizer.tokenize(programtext)
            programast = javalang.parser.parse(programtokens)
            paths.append(file)
            asts.append(programast)
            get_sequence(programast, alltokens)
            programfile.close()
        except:
            err.append(file)
    if len(err) != 0:
        print("Err file: ", err)

    astdict = dict(zip(paths, asts))
    ifcount = 0
    whilecount = 0
    forcount = 0
    blockcount = 0
    docount = 0
    switchcount = 0
    for token in alltokens:
        if token == 'IfStatement':
            ifcount += 1
        if token == 'WhileStatement':
            whilecount += 1
        if token == 'ForStatement':
            forcount += 1
        if token == 'BlockStatement':
            blockcount += 1
        if token == 'DoStatement':
            docount += 1
        if token == 'SwitchStatement':
            switchcount += 1
    print(ifcount, whilecount, forcount, blockcount, docount, switchcount)
    print('allnodes ', len(alltokens))
    alltokens = list(set(alltokens))
    vocabsize = len(alltokens)
    tokenids = range(vocabsize)
    vocabdict = dict(zip(alltokens, tokenids))
    print('vocab size: ', vocabsize)
    return astdict, vocabsize, vocabdict


def createseparategraph(astdict, vocablen, vocabdict, device, mode='astonly', nextsib=False, ifedge=False,
                        whileedge=False, foredge=False, blockedge=False, nexttoken=False, nextuse=False):
    pathlist = []
    treelist = []
    print('nextsib ', nextsib)
    print('ifedge ', ifedge)
    print('whileedge ', whileedge)
    print('foredge ', foredge)
    print('blockedge ', blockedge)
    print('nexttoken', nexttoken)
    print('nextuse ', nextuse)
    print(len(astdict))
    for path, tree in astdict.items():
        # print(tree)
        # print(path)
        nodelist = []
        newtree = AnyNode(id=0, token=None, data=None)
        createtree(newtree, tree, nodelist)
        # print(path)
        # print(newtree)
        x = []
        edgesrc = []
        edgetgt = []
        edge_attr = []
        if mode == 'astonly':
            getnodeandedge_astonly(newtree, x, vocabdict, edgesrc, edgetgt)
        else:
            getnodeandedge(newtree, x, vocabdict, edgesrc, edgetgt, edge_attr)
            if nextsib == True:
                getedge_nextsib(newtree, vocabdict, edgesrc, edgetgt, edge_attr)
            getedge_flow(newtree, vocabdict, edgesrc, edgetgt, edge_attr, ifedge, whileedge, foredge)
            if blockedge == True:
                getedge_nextstmt(newtree, vocabdict, edgesrc, edgetgt, edge_attr)
            tokenlist = []
            if nexttoken == True:
                getedge_nexttoken(newtree, vocabdict, edgesrc, edgetgt, edge_attr, tokenlist)
            variabledict = {}
            if nextuse == True:
                getedge_nextuse(newtree, vocabdict, edgesrc, edgetgt, edge_attr, variabledict)
        # x = torch.tensor(x, dtype=torch.long, device=device)
        edge_index = [edgesrc, edgetgt]
        # edge_index = torch.tensor([edgesrc, edgetgt], dtype=torch.long, device=device)
        astlength = len(x)
        # print(x)
        # print(edge_index)
        # print(edge_attr)
        pathlist.append(path)
        treelist.append([[x, edge_index, edge_attr], astlength])
        astdict[path] = [[x, edge_index, edge_attr], astlength]
    # treedict=dict(zip(pathlist,treelist))
    # print(totalif,totalwhile,totalfor,totalblock)
    return astdict


def creategmndata(dataset, split, cross, treedict, vocablen, vocabdict, device):

    train_list, val_list, test_list = get_train_test_data(dataset=dataset, split=split, cross=cross)
    print("data shape:", len(train_list), len(test_list))
    train_data = createpairdata(treedict, train_list, device=device)
    val_data = None
    if val_list:
        val_data = createpairdata(treedict, val_list, device=device)
    test_data = createpairdata(treedict, test_list, device=device)
    return train_data, val_data, test_data


def createpairdata(treedict, pathlist, device):
    datalist = []
    countlines = 1
    exist_paths = treedict.keys()
    for line in pathlist:
        # print(countlines)
        countlines += 1
        code1path = line[0]
        code2path = line[1]
        label = int(line[2])
        if (code1path not in exist_paths) or (code2path not in exist_paths):
            continue
        data1 = treedict[code1path]
        data2 = treedict[code2path]
        x1, edge_index1, edge_attr1, ast1length = data1[0][0], data1[0][1], data1[0][2], data1[1]
        x2, edge_index2, edge_attr2, ast2length = data2[0][0], data2[0][1], data2[0][2], data2[1]
        '''matchsrc = []
        matchtgt = []
        for i in range(ast1length):
            for j in range(ast2length):
                matchsrc.append(i)
                matchtgt.append(j)
        match_index=[matchsrc, matchtgt]'''
        # match_index = torch.tensor([matchsrc, matchtgt], dtype=torch.long, device=device)
        if edge_attr1 == []:
            edge_attr1 = None
            edge_attr2 = None
        data = [[x1, x2, edge_index1, edge_index2, edge_attr1, edge_attr2], label]
        datalist.append(data)
    return datalist


if __name__ == '__main__':
    astdict, vocabsize, vocabdict = createast()
    treedict = createseparategraph(astdict, vocabsize, vocabdict, device='cpu', mode='else', nextsib=True, ifedge=True,
                                   whileedge=True, foredge=True, blockedge=True, nexttoken=True, nextuse=True)
    # creategmndata(treedict,vocabsize,vocabdict,device='cpu')
