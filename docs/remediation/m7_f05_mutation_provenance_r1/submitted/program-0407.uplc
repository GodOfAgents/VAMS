(program
  1.1.0
[   [
    [
      (lam
        i_0
        (lam
          i_1
          (lam
            i_2
            (case
              (constr
                0
              (force (builtin tailList))
              (force (builtin headList))
              (force (force (builtin chooseList)))
              (force (force (builtin sndPair)))
              (force (force (builtin fstPair)))
              (force (builtin ifThenElse))
              [ (builtin unListData) i_1 ])
            (lam
              i_3
              (lam
                i_4
                (lam
                  i_5
                  (lam
                    i_6
                    (lam
                      i_7
                      (lam
                        i_8
                        (lam
                          i_9
                          (force
                            (case
                              (constr
                                0
                              [
                                (lam
                                  i_10
                                  [
                                    (lam
                                      i_11
                                      (case
                                        (constr
                                          0
                                        [ i_4 i_11 ]
                                        [ i_4 [ i_3 i_11 ] ]
                                        [ i_4 i_10 ])
                                      (lam
                                        i_12
                                        (lam
                                          i_13
                                          (lam
                                            i_14
                                            (force
                                              (case
                                                (constr
                                                  0
                                                [
                                                  [
                                                    (builtin equalsInteger)
                                                    (con integer 0)
                                                  ]
                                                  [
                                                    i_7
                                                    [
                                                      (builtin unConstrData)
                                                      i_13
                                                    ]
                                                  ]
                                                ]
                                                (delay
                                                  [
                                                    (lam
                                                      i_15
                                                      (force
                                                        (case
                                                          (constr
                                                            0
                                                          [
                                                            [
                                                              (builtin
                                                                equalsInteger
                                                              )
                                                              (con integer 0)
                                                            ]
                                                            [
                                                              i_7
                                                              [
                                                                (builtin
                                                                  unConstrData
                                                                )
                                                                i_12
                                                              ]
                                                            ]
                                                          ]
                                                          (delay
                                                            [
                                                              (lam
                                                                i_16
                                                                (force
                                                                  (case
                                                                    (constr
                                                                      0
                                                                    [ i_3 i_16 ]
                                                                    (delay
                                                                      [
                                                                        (lam
                                                                          i_17
                                                                          [
                                                                            [
                                                                              i_17
                                                                              i_17
                                                                            ]
                                                                            [
                                                                              (builtin
                                                                                unListData
                                                                              )
                                                                              [
                                                                                i_4
                                                                                i_16
                                                                              ]
                                                                            ]
                                                                          ]
                                                                        )
                                                                        (lam
                                                                          i_18
                                                                          (lam
                                                                            i_19
                                                                            (force
                                                                              (case
                                                                                (constr
                                                                                  0
                                                                                i_19
                                                                                (delay
                                                                                  (con
                                                                                    bool
                                                                                    True
                                                                                  )
                                                                                )
                                                                                (delay
                                                                                  [
                                                                                    (lam
                                                                                      i_20
                                                                                      [
                                                                                        [
                                                                                          i_18
                                                                                          i_18
                                                                                        ]
                                                                                        [
                                                                                          i_3
                                                                                          i_19
                                                                                        ]
                                                                                      ]
                                                                                    )
                                                                                    [
                                                                                      (builtin
                                                                                        unBData
                                                                                      )
                                                                                      [
                                                                                        i_4
                                                                                        i_19
                                                                                      ]
                                                                                    ]
                                                                                  ]
                                                                                ))
                                                                              i_5)
                                                                            )
                                                                          )
                                                                        )
                                                                      ]
                                                                    )
                                                                    (delay
                                                                      (error )
                                                                    ))
                                                                  i_5)
                                                                )
                                                              )
                                                              [
                                                                i_6
                                                                [
                                                                  (builtin
                                                                    unConstrData
                                                                  )
                                                                  i_12
                                                                ]
                                                              ]
                                                            ]
                                                          )
                                                          (delay (error )))
                                                        i_8)
                                                      )
                                                    )
                                                    [
                                                      (builtin unBData)
                                                      [
                                                        i_4
                                                        [
                                                          i_6
                                                          [
                                                            (builtin
                                                              unConstrData
                                                            )
                                                            i_13
                                                          ]
                                                        ]
                                                      ]
                                                    ]
                                                  ]
                                                )
                                                (delay (error )))
                                              i_8)
                                            )
                                          )
                                        )
                                      ))
                                    )
                                    [ i_3 i_10 ]
                                  ]
                                )
                                [ i_6 [ (builtin unConstrData) i_2 ] ]
                              ]
                              (delay (con unit ()))
                              (delay [ (error ) (force (error )) ]))
                            i_8)
                          )
                        )
                      )
                    )
                  )
                )
              )
            ))
          )
        )
      )
      (con
        data (Constr 0 [B #aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, I 7])
      )
    ]
    (con
      data (List [B #237591b8040884423548673b95e912b492b34c5dff5f817b57761460d68c3b93, B #81eabfc332f1dd64335c7362db7d974595d1b286bf9e39a1dc94ec5ab447059a, B #68a8fb50f1f5de37ccc4582f14eeee0e85d85ecc8a7d9aeffc2e1c8537667069, B #8339da8dd35b68160427bb05055677030a734ec51e2e21b667d25a086f7f1698, B #adfdb0f1d3d24dc3ac3b12e3c5f876519dfb348c496d18c861546ca70d57d011])
    )
  ]
 (con data (Constr 0 [Constr 0 [List [Constr 0 [Constr 0 [B #aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, I 7], Constr 0 [Constr 0 [Constr 0 [B #61616161616161616161616161616161616161616161616161616161], Constr 1 []], Map [(B #, Map [(B #, I 2000000)])], Constr 0 [], Constr 1 []]], Constr 0 [Constr 0 [B #bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, I 3], Constr 0 [Constr 0 [Constr 0 [B #61616161616161616161616161616161616161616161616161616161], Constr 1 []], Map [(B #, Map [(B #, I 15000000)])], Constr 0 [], Constr 1 []]]], List [], List [Constr 0 [Constr 0 [Constr 1 [B #b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66], Constr 1 []], Map [(B #, Map [(B #, I 10000000)]), (B #0d0ac1d72c5632676ec41e04196d323944bbea4e592fb1ce7fdb9356, Map [(B #56414d532d4630352d415554482d5633, I 1)])], Constr 2 [Constr 0 [I 3, B #aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, I 7, I 0, List [B #237591b8040884423548673b95e912b492b34c5dff5f817b57761460d68c3b93, B #81eabfc332f1dd64335c7362db7d974595d1b286bf9e39a1dc94ec5ab447059a, B #68a8fb50f1f5de37ccc4582f14eeee0e85d85ecc8a7d9aeffc2e1c8537667069, B #8339da8dd35b68160427bb05055677030a734ec51e2e21b667d25a086f7f1698, B #adfdb0f1d3d24dc3ac3b12e3c5f876519dfb348c496d18c861546ca70d57d011], I 3, Constr 0 [], Constr 0 [Constr 0 [], I 0, I 0, I 0, I 0, I 0, B #00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000]]], Constr 1 []], Constr 0 [Constr 0 [Constr 0 [B #62626262626262626262626262626262626262626262626262626262], Constr 1 []], Map [(B #, Map [(B #, I 6000000)])], Constr 2 [Constr 0 [I 3, B #aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, I 7, I 0, List [B #237591b8040884423548673b95e912b492b34c5dff5f817b57761460d68c3b93, B #81eabfc332f1dd64335c7362db7d974595d1b286bf9e39a1dc94ec5ab447059a, B #68a8fb50f1f5de37ccc4582f14eeee0e85d85ecc8a7d9aeffc2e1c8537667069, B #8339da8dd35b68160427bb05055677030a734ec51e2e21b667d25a086f7f1698, B #adfdb0f1d3d24dc3ac3b12e3c5f876519dfb348c496d18c861546ca70d57d011], I 3, Constr 0 [], Constr 0 [Constr 0 [], I 0, I 0, I 0, I 0, I 0, B #00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000]]], Constr 1 []]], I 1000000, Map [(B #0d0ac1d72c5632676ec41e04196d323944bbea4e592fb1ce7fdb9356, Map [(B #56414d532d4630352d415554482d5633, I 1)])], List [], Map [], Constr 0 [Constr 0 [Constr 1 [I 1700000000000], Constr 1 []], Constr 0 [Constr 1 [I 1700000030000], Constr 1 []]], List [B #63636363636363636363636363636363636363636363636363636363], Map [], Map [], B #cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc, Map [], List [], Constr 1 [], Constr 1 []], Constr 0 [List [B #512a86c9de10d1d9e4ada4f9110559134b357871a2af8c22f24457677d1111f723c7f96558f8f0f52a9f25c1045f8805411e057efea1a46fbce65386fac5ac07, B #c964bc0f2c6eb1645ea99852193bdad467113eddd5fc14b5efefb5d94da52e611a290546a816df362e36d8dd861b16110f8982fce21fae967bb3068f05ed880f, B #ff44c99ddfc5c7489b489e8c00d46c2b3a6f3650a2251fb1a115613fd2e9f5091da4fef39951846ce78c00c39058201552e725b58a0b195665fc9729b0678601, B #2bbd3d704914ae451980897f565af3e440ef07ca2d1cce34e703c772f7efc8dddd25558e294f3a4ced780b5265acbe014b5364cd69af7c2f2ae959fcfb6c710c, B #fcf31122bf60ba052ae868805c67a509466a3c713d979a6fc8369cd4427e448fa5bf784b772843622ab7f1cdc3904bda0e5e291813a95f503fdee321dce0bd02]], Constr 0 [B #0d0ac1d72c5632676ec41e04196d323944bbea4e592fb1ce7fdb9356]])) ]
)
